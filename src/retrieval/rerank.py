"""
Cross-Encoder Reranker over IS Code Chunks using BAAI/bge-reranker-base.
Reranks top-5 candidate chunks from hybrid retrieval.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from sentence_transformers import CrossEncoder
from src.retrieval.hybrid_search import search as hybrid_search

CHUNKS_PATH = Path("data/processed/chunks.jsonl")
MODEL_NAME = "BAAI/bge-reranker-base"


class Reranker:
    def __init__(self, model_name: str = MODEL_NAME, chunks_path: Path = CHUNKS_PATH):
        self.model_name = model_name
        self.chunks_path = Path(chunks_path)
        self.chunk_by_id: Dict[str, Dict[str, Any]] = {}
        self.chunk_text_by_id: Dict[str, str] = {}
        self.model: Optional[CrossEncoder] = None

        self._load_chunks()
        self._load_model()

    def _load_chunks(self) -> None:
        if not self.chunks_path.exists():
            raise FileNotFoundError(f"Chunks file not found at {self.chunks_path}")

        with open(self.chunks_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    chunk = json.loads(line.strip())
                    cid = chunk["chunk_id"]
                    self.chunk_by_id[cid] = chunk

                    context = chunk.get("context_path") or ""
                    title = chunk.get("title") or ""
                    text = chunk.get("text") or ""
                    self.chunk_text_by_id[cid] = f"{context} {title} {text}".strip()

    def _load_model(self) -> None:
        print(f"Loading CrossEncoder model: {self.model_name}...")
        self.model = CrossEncoder(self.model_name)
        print("CrossEncoder model loaded successfully.")

    def search(self, query: str, k: int = 3, top_n_hybrid: int = 5) -> List[Dict[str, Any]]:
        if not query.strip():
            return []

        # 1. Retrieve top-N candidate chunks from hybrid search
        hybrid_candidates = hybrid_search(query, k=top_n_hybrid)
        if not hybrid_candidates:
            return []

        # 2. Build (query, chunk_text) pairs for scoring
        pairs = []
        for cand in hybrid_candidates:
            cid = cand["chunk_id"]
            chunk_text = self.chunk_text_by_id.get(cid, "")
            pairs.append([query, chunk_text])

        # 3. Predict relevance scores with CrossEncoder
        scores = self.model.predict(pairs)

        # 4. Construct scored items
        scored_items = []
        for idx, cand in enumerate(hybrid_candidates):
            cid = cand["chunk_id"]
            scored_items.append({
                "chunk_id": cid,
                "citation": cand.get("citation", cid),
                "score": float(scores[idx]),
                "hybrid_rank": idx + 1,
                "bm25_rank": cand.get("bm25_rank"),
                "dense_rank": cand.get("dense_rank"),
            })

        # 5. Sort descending by reranker score
        scored_items.sort(key=lambda x: x["score"], reverse=True)
        return scored_items[:k]


# Module-level singleton
_reranker: Optional[Reranker] = None


def get_reranker() -> Reranker:
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker


def search(query: str, k: int = 3, top_n_hybrid: int = 5) -> List[Dict[str, Any]]:
    return get_reranker().search(query, k=k, top_n_hybrid=top_n_hybrid)


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "maximum tension reinforcement in a beam"
    print(f"Query: {q}")
    for rank, res in enumerate(search(q, k=3), 1):
        print(
            f"  {rank}. [{res['score']:.4f}] {res['chunk_id']} "
            f"(Hybrid rank: {res['hybrid_rank']}) - {res['citation']}"
        )
