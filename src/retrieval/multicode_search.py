"""
Multi-Standard Structural IS Code Retrieval Engine.

Step 5: Embedding & Vector Indexing
Step 6: Retrieval System

Supports multi-standard hybrid search across:
- IS 456:2000 (Plain & Reinforced Concrete)
- IS 13920:2016 (Seismic Ductile Detailing)
- IS 1893 (Part 1):2016 (Criteria for Earthquake Resistant Design)
- IS 875 (Part 2):1987 (Occupancy Imposed / Live Loads)
- IS 800:2007 (General Construction In Steel)

Search Architecture:
- Lexical Engine: BM25Okapi with engineering domain tokenizer (preserves clause decimals and standards).
- Dense Vector Store: Qdrant Local Client (BGE-small 384-dimensional dense semantic embeddings).
- Hybrid Fusion: Reciprocal Rank Fusion (RRF k=60) combining keyword precision with semantic depth.
- Standard-specific filtering (e.g. 'IS 13920', 'IS 1893', 'IS 875', 'IS 800', 'IS 456') or cross-code federated retrieval.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
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
    """Multi-code hybrid indexing and search engine for Indian Standards."""

    def __init__(self):
        self.corpus: List[Dict[str, Any]] = load_all_structural_chunks()
        self._build_bm25_indices()
        self.qdrant = get_qdrant_db()

    def _build_bm25_indices(self) -> None:
        """Builds global BM25 search index over unified structural corpus."""
        tokenized_corpus = [custom_engineering_tokenizer(item["text"]) for item in self.corpus]
        self.bm25 = BM25Okapi(tokenized_corpus) if tokenized_corpus else None

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
                "clause": item["clause"],
                "title": item["title"],
                "citation": item["citation"],
                "text": item["text"],
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

    def search(
        self,
        query: str,
        code_filter: Optional[str] = None,
        top_k: int = 3,
        mode: str = "hybrid",
        rrf_k: int = 60,
    ) -> List[Dict[str, Any]]:
        """
        Executes search over structural standards.
        Modes:
        - 'hybrid' (default): Reciprocal Rank Fusion (RRF) combining BM25 lexical & Qdrant dense semantic vectors.
        - 'dense' or 'qdrant': Dense vector search only.
        - 'bm25' or 'lexical': Lexical BM25 search only.
        """
        if not query.strip():
            return []

        if mode in ("bm25", "lexical"):
            return self.search_bm25(query=query, code_filter=code_filter, top_k=top_k)

        if mode in ("qdrant", "dense"):
            return self.search_qdrant(query=query, code_filter=code_filter, top_k=top_k)

        # Hybrid RRF Fusion
        candidate_limit = max(top_k * 3, 10)
        bm25_hits = self.search_bm25(query=query, code_filter=code_filter, top_k=candidate_limit)
        qdrant_hits = self.search_qdrant(query=query, code_filter=code_filter, top_k=candidate_limit)

        if not bm25_hits and not qdrant_hits:
            return []
        if not bm25_hits:
            return qdrant_hits[:top_k]
        if not qdrant_hits:
            return bm25_hits[:top_k]

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
        for cid in ranked_cids[:top_k]:
            item = items_by_id[cid].copy()
            item["score"] = round(float(rrf_scores[cid]), 5)
            hybrid_results.append(item)

        return hybrid_results


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
) -> List[Dict[str, Any]]:
    """Public helper function for multi-code retrieval across all 5 Indian Standards."""
    retriever = get_multicode_retriever()
    return retriever.search(query=query, code_filter=code_filter, top_k=top_k, mode=mode)
