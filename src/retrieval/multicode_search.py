"""
Multi-Standard Structural IS Code Retrieval Engine.

Step 5: Embedding & Vector Indexing
Step 6: Retrieval System

Supports multi-standard hybrid search across:
- IS 456:2000 (Plain & Reinforced Concrete)
- IS 13920:2016 (Seismic Ductile Detailing)
- IS 1893 (Part 1):2016 (Criteria for Earthquake Resistant Design)
- IS 875 (Parts 1, 2, 3) (Dead, Imposed, and Wind Loads)
- IS 800:2007 (General Construction In Steel)
- Official BIS Amendments & Errata
- SP:16 & IITK-GSDMA Design Examples

Search Architecture:
- Lexical Engine: BM25Okapi with engineering domain tokenizer (preserves clause decimals and standards).
- Dense Vector Store: Qdrant Local Client (BGE-small 384-dimensional dense semantic embeddings).
- Hybrid Fusion: Reciprocal Rank Fusion (RRF k=60) combining keyword precision with semantic depth.
- Cross-Encoder Reranking: BAAI/bge-reranker-base (with optional Cohere Rerank API adapter).
- Standard-specific filtering (e.g. 'IS 13920', 'IS 1893', 'IS 875', 'IS 800', 'IS 456') or cross-code federated retrieval.
- Returns top-k clauses with exact citations, metadata, and calibrated confidence scores.
"""

import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np
from rank_bm25 import BM25Okapi

from src.retrieval.qdrant_db import load_all_structural_chunks, get_qdrant_db


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


def custom_engineering_tokenizer(text: str) -> List[str]:
    """Tokenizes structural engineering text preserving standard numbers, decimal clauses, and hyphenations."""
    cleaned = text.lower().replace(":", " ").replace("/", " ").replace("(", " ").replace(")", " ")
    tokens = [t.strip(",.;-_\"' ") for t in cleaned.split()]
    return [t for t in tokens if len(t) > 1]


class MultiCodeRetriever:
    """Multi-code hybrid indexing and search engine with cross-encoder reranking for Indian Standards."""

    def __init__(self):
        self.corpus: List[Dict[str, Any]] = load_all_structural_chunks()
        self._build_bm25_indices()
        self.qdrant = get_qdrant_db()
        self._cross_encoder = None

    def _build_bm25_indices(self) -> None:
        """Builds global BM25 search index over unified structural corpus."""
        tokenized_corpus = [custom_engineering_tokenizer(item["text"]) for item in self.corpus]
        self.bm25 = BM25Okapi(tokenized_corpus) if tokenized_corpus else None

    def _get_cross_encoder(self):
        if self._cross_encoder is None:
            from sentence_transformers import CrossEncoder
            model_name = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-base")
            self._cross_encoder = CrossEncoder(model_name)
        return self._cross_encoder

    def search_bm25(
        self,
        query: str,
        code_filter: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Executes BM25 lexical search over the structural corpus."""
        if not self.corpus or not self.bm25 or not query.strip():
            return []

        tokens = custom_engineering_tokenizer(query)
        scores = self.bm25.get_scores(tokens)
        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

        results = []
        for idx in ranked_indices:
            item = self.corpus[idx]
            score = scores[idx]

            if score <= 0.001:
                continue

            if code_filter and code_filter.lower() not in item["code"].lower():
                continue

            results.append({
                "chunk_id": item["chunk_id"],
                "code": item["code"],
                "year": item.get("year"),
                "amendment": item.get("amendment"),
                "section": item.get("section"),
                "clause": item["clause"],
                "title": item["title"],
                "citation": item["citation"],
                "text": item["text"],
                "category": item.get("category", "clause"),
                "applicability": item.get("applicability"),
                "keywords": item.get("keywords", []),
                "dependencies": item.get("dependencies", []),
                "verified": item.get("verified", False),
                "score": round(float(score), 4),
            })

            if len(results) >= top_k:
                break

        return results

    def search_qdrant(
        self,
        query: str,
        code_filter: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Executes dense semantic search using embedded Qdrant vector database."""
        return self.qdrant.search(query=query, code_filter=code_filter, top_k=top_k)

    def rerank_candidates(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Reranks hybrid candidates using cross-encoder (BGE-reranker or Cohere)
        and computes calibrated confidence scores.
        """
        if not candidates or not query.strip():
            return candidates[:top_k]

        # Check for Cohere API key if user configured external service
        cohere_key = os.getenv("COHERE_API_KEY")
        if cohere_key:
            try:
                import httpx
                resp = httpx.post(
                    "https://api.cohere.com/v1/rerank",
                    headers={"Authorization": f"Bearer {cohere_key}", "Content-Type": "application/json"},
                    json={
                        "model": "rerank-english-v3.0",
                        "query": query,
                        "documents": [f"{c.get('code', '')} {c.get('clause', '')}: {c.get('text', '')}" for c in candidates],
                        "top_n": top_k,
                    },
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    cohere_data = resp.json()
                    reranked = []
                    for item in cohere_data.get("results", []):
                        idx = item["index"]
                        cand = candidates[idx].copy()
                        cand["rerank_score"] = float(item["relevance_score"])
                        cand["confidence_score"] = round(float(item["relevance_score"]), 4)
                        cand["score"] = round(float(item["relevance_score"]), 4)
                        reranked.append(cand)
                    return reranked
            except Exception:
                pass  # Fall back to local CrossEncoder

        # Local BGE CrossEncoder
        encoder = self._get_cross_encoder()
        pairs = [
            [query, f"{c.get('code', '')} {c.get('clause', '')} {c.get('title', '')}: {c.get('text', '')}"]
            for c in candidates
        ]
        scores = encoder.predict(pairs)

        reranked = []
        for idx, cand in enumerate(candidates):
            raw_score = float(scores[idx])
            conf = 1.0 / (1.0 + np.exp(-raw_score))
            c_copy = cand.copy()
            c_copy["hybrid_rank"] = idx + 1
            c_copy["rerank_score"] = round(raw_score, 4)
            c_copy["confidence_score"] = round(float(conf), 4)
            c_copy["score"] = round(float(conf), 4)
            reranked.append(c_copy)

        reranked.sort(key=lambda x: x["rerank_score"], reverse=True)
        return reranked[:top_k]

    def search(
        self,
        query: str,
        code_filter: Optional[str] = None,
        top_k: int = 3,
        mode: str = "hybrid",
        rerank: bool = False,
        rrf_k: int = 60,
    ) -> List[Dict[str, Any]]:
        """
        Executes search over structural standards.
        Modes:
        - 'hybrid' (default): Reciprocal Rank Fusion (RRF) combining BM25 lexical & Qdrant dense semantic vectors.
        - 'rerank' or 'hybrid_rerank': Hybrid retrieval followed by Cross-Encoder reranking.
        - 'dense' or 'qdrant': Dense vector search only.
        - 'bm25' or 'lexical': Lexical BM25 search only.
        """
        if not query.strip():
            return []

        if mode in ("bm25", "lexical"):
            return self.search_bm25(query=query, code_filter=code_filter, top_k=top_k)

        if mode in ("qdrant", "dense"):
            return self.search_qdrant(query=query, code_filter=code_filter, top_k=top_k)

        should_rerank = rerank or mode in ("rerank", "hybrid_rerank")

        # Hybrid RRF Fusion
        candidate_limit = max(top_k * 3, 10) if should_rerank else max(top_k * 2, 5)
        bm25_hits = self.search_bm25(query=query, code_filter=code_filter, top_k=candidate_limit)
        qdrant_hits = self.search_qdrant(query=query, code_filter=code_filter, top_k=candidate_limit)

        if not bm25_hits and not qdrant_hits:
            return []
        if not bm25_hits:
            hits = qdrant_hits
            return self.rerank_candidates(query, hits, top_k=top_k) if should_rerank else hits[:top_k]
        if not qdrant_hits:
            hits = bm25_hits
            return self.rerank_candidates(query, hits, top_k=top_k) if should_rerank else hits[:top_k]

        # Calculate RRF scores
        rrf_scores: Dict[str, float] = {}
        items_by_id: Dict[str, Dict[str, Any]] = {}

        for rank, hit in enumerate(bm25_hits):
            cid = hit["chunk_id"]
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (rrf_k + rank + 1))
            items_by_id[cid] = hit

        for rank, hit in enumerate(qdrant_hits):
            cid = hit["chunk_id"]
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (rrf_k + rank + 1))
            if cid not in items_by_id:
                items_by_id[cid] = hit

        ranked_cids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)

        hybrid_results = []
        for cid in ranked_cids:
            item = items_by_id[cid].copy()
            item["score"] = round(float(rrf_scores[cid]), 5)
            hybrid_results.append(item)

        if should_rerank:
            return self.rerank_candidates(query=query, candidates=hybrid_results[:candidate_limit], top_k=top_k)

        return hybrid_results[:top_k]


# Global singleton
_GLOBAL_MULTICODE_RETRIEVER: Optional[MultiCodeRetriever] = None


def get_multicode_retriever() -> MultiCodeRetriever:
    global _GLOBAL_MULTICODE_RETRIEVER
    if _GLOBAL_MULTICODE_RETRIEVER is None:
        _GLOBAL_MULTICODE_RETRIEVER = MultiCodeRetriever()
    return _GLOBAL_MULTICODE_RETRIEVER


def retrieve_multicode(
    query: str,
    code_filter: Optional[str] = None,
    top_k: int = 3,
    mode: str = "hybrid",
    rerank: bool = False,
) -> List[Dict[str, Any]]:
    """Public helper function for multi-code retrieval across all Indian Standards."""
    retriever = get_multicode_retriever()
    return retriever.search(query=query, code_filter=code_filter, top_k=top_k, mode=mode, rerank=rerank)


if __name__ == "__main__":
    import sys

    q = sys.argv[1] if len(sys.argv) > 1 else "nominal cover for moderate exposure"
    print(f"\n=======================================================")
    print(f"TESTING RETRIEVAL FOR: \"{q}\"")
    print(f"=======================================================\n")
    results = retrieve_multicode(q, top_k=2, mode="hybrid")
    for i, r in enumerate(results, 1):
        print(f"Result #{i}:")
        print(f"  Clause ID : {r.get('chunk_id')}")
        print(f"  Standard  : {r.get('code')}")
        print(f"  Title     : {r.get('title')}")
        print(f"  Score     : {r.get('score')}")
        snippet = (r.get('text') or '').replace('\n', ' ')[:160]
        print(f"  Snippet   : {snippet}...\n")

