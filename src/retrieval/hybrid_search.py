"""
Hybrid Retrieval over IS Code Chunks combining BM25 and Dense Retrieval using Reciprocal Rank Fusion (RRF).
Formula: score = 1 / (60 + rank_bm25) + 1 / (60 + rank_dense)
"""

from typing import List, Dict, Any, Optional
from src.retrieval.bm25_search import search as bm25_search, get_searcher as get_bm25_searcher
from src.retrieval.dense_search import search as dense_search, get_searcher as get_dense_searcher

RRF_K = 60


class HybridSearcher:
    def __init__(self, rrf_k: int = RRF_K):
        self.rrf_k = rrf_k
        self.bm25_searcher = get_bm25_searcher()
        self.dense_searcher = get_dense_searcher()

    def search(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        if not query.strip():
            return []

        num_chunks = len(self.bm25_searcher.chunks)

        # Retrieve full ranked lists from BM25 and Dense retrievers
        bm25_results = self.bm25_searcher.search(query, k=num_chunks)
        dense_results = self.dense_searcher.search(query, k=num_chunks)

        # Rank maps (1-indexed)
        bm25_ranks: Dict[str, int] = {
            r["chunk_id"]: idx for idx, r in enumerate(bm25_results, 1)
        }
        dense_ranks: Dict[str, int] = {
            r["chunk_id"]: idx for idx, r in enumerate(dense_results, 1)
        }

        # Citation map from either result list
        citations: Dict[str, str] = {}
        for r in bm25_results:
            citations[r["chunk_id"]] = r.get("citation", r["chunk_id"])
        for r in dense_results:
            citations[r["chunk_id"]] = r.get("citation", citations.get(r["chunk_id"], r["chunk_id"]))

        # Compute Reciprocal Rank Fusion score for all chunks
        all_chunk_ids = set(bm25_ranks.keys()).union(set(dense_ranks.keys()))
        fused_items = []
        for cid in all_chunk_ids:
            r_bm25 = bm25_ranks.get(cid, num_chunks + 1)
            r_dense = dense_ranks.get(cid, num_chunks + 1)
            fused_score = (1.0 / (self.rrf_k + r_bm25)) + (1.0 / (self.rrf_k + r_dense))
            fused_items.append({
                "chunk_id": cid,
                "citation": citations.get(cid, cid),
                "score": fused_score,
                "bm25_rank": r_bm25,
                "dense_rank": r_dense,
            })

        # Sort descending by fused score
        fused_items.sort(key=lambda x: x["score"], reverse=True)
        return fused_items[:k]


# Module-level singleton
_hybrid_searcher: Optional[HybridSearcher] = None


def get_searcher() -> HybridSearcher:
    global _hybrid_searcher
    if _hybrid_searcher is None:
        _hybrid_searcher = HybridSearcher()
    return _hybrid_searcher


def search(query: str, k: int = 3) -> List[Dict[str, Any]]:
    return get_searcher().search(query, k=k)


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "maximum tension reinforcement in a beam"
    print(f"Query: {q}")
    for rank, res in enumerate(search(q, k=3), 1):
        print(
            f"  {rank}. [{res['score']:.6f}] {res['chunk_id']} "
            f"(BM25 rank: {res['bm25_rank']}, Dense rank: {res['dense_rank']})"
        )
