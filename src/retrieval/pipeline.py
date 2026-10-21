"""
Unified Production Retrieval Pipeline for IS 456 RAG.
Combines BM25, Dense embeddings, Reciprocal Rank Fusion, and Cross-Encoder Reranking.
Returns clean, verified chunks with original text directly from chunks.jsonl.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.retrieval.rerank import get_reranker

CHUNKS_PATH = Path("data/processed/chunks.jsonl")

# Cached chunk store loaded once from chunks.jsonl
_chunks_by_id: Optional[Dict[str, Dict[str, Any]]] = None


def _get_chunks_map() -> Dict[str, Dict[str, Any]]:
    global _chunks_by_id
    if _chunks_by_id is None:
        if not CHUNKS_PATH.exists():
            raise FileNotFoundError(f"Chunks file not found at {CHUNKS_PATH}")
        _chunks_by_id = {}
        with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    chunk = json.loads(line.strip())
                    _chunks_by_id[chunk["chunk_id"]] = chunk
    return _chunks_by_id


def retrieve(query: str, k: int = 3) -> List[Dict[str, Any]]:
    """
    Executes hybrid retrieval (BM25 + Dense RRF) followed by Cross-Encoder reranking.
    Returns the top-k chunks with full metadata and verified text directly from chunks.jsonl.

    Args:
        query: User question or search text.
        k: Number of top results to return (default 3).

    Returns:
        List of dicts containing chunk_id, citation, chunk_type, title, text,
        context_path, page_number, cross_references, rerank_score, hybrid_rank, verified.
    """
    if not query.strip():
        return []

    # Models and chunk metadata are loaded once at first call and cached
    reranker = get_reranker()
    chunks_map = _get_chunks_map()

    # Rerank candidates: candidate pool is at least top-5 or k, whichever is larger
    top_candidates = max(5, k)
    reranked_results = reranker.search(query, k=k, top_n_hybrid=top_candidates)

    output = []
    for res in reranked_results:
        cid = res["chunk_id"]
        raw_chunk = chunks_map.get(cid, {})

        # Build output dictionary with text sourced strictly from chunks.jsonl
        output.append({
            "chunk_id": raw_chunk.get("chunk_id", cid),
            "citation": raw_chunk.get("citation", res.get("citation", cid)),
            "chunk_type": raw_chunk.get("chunk_type"),
            "title": raw_chunk.get("title"),
            "text": raw_chunk.get("text", ""),  # Text directly from chunks.jsonl
            "context_path": raw_chunk.get("context_path"),
            "page_number": raw_chunk.get("page_number", []),
            "cross_references": raw_chunk.get("cross_references", []),
            # rerank_score: ranking score from CrossEncoder, not a probability
            "rerank_score": float(res["score"]),
            "hybrid_rank": res["hybrid_rank"],
            "verified": raw_chunk.get("verified", False),
        })

    return output


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    question = (
        " ".join(sys.argv[1:])
        if len(sys.argv) > 1
        else "maximum tension reinforcement in a beam"
    )
    results = retrieve(question, k=3)
    print(json.dumps(results, indent=2, ensure_ascii=False))
