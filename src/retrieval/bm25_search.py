"""
BM25 Keyword Retrieval over IS Code Chunks.
"""

import json
from pathlib import Path
import re
from typing import List, Dict, Any
from rank_bm25 import BM25Okapi

CHUNKS_PATH = Path("data/processed/chunks.jsonl")


def tokenize(text: str) -> List[str]:
    """
    Tokenizes text by lowercasing and splitting on non-alphanumeric characters,
    preserving decimal numbers and clause numbers (e.g. '26.5.1.6', '0.04').
    """
    return re.findall(r"\d+(?:\.\d+)+|\w+", text.lower())


class BM25Searcher:
    def __init__(self, chunks_file: Path = CHUNKS_PATH):
        self.chunks_file = Path(chunks_file)
        self.chunks: List[Dict[str, Any]] = []
        self.corpus_tokens: List[List[str]] = []
        self.bm25: BM25Okapi = None
        self._load_and_index()

    def _load_and_index(self) -> None:
        if not self.chunks_file.exists():
            raise FileNotFoundError(f"Chunks file not found at {self.chunks_file}")

        self.chunks = []
        self.corpus_tokens = []

        with open(self.chunks_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    chunk = json.loads(line.strip())
                    self.chunks.append(chunk)
                    # Index over context_path, title and text
                    context = chunk.get("context_path") or ""
                    title = chunk.get("title") or ""
                    text = chunk.get("text") or ""
                    combined_text = f"{context} {title} {text}".strip()
                    tokens = tokenize(combined_text)
                    self.corpus_tokens.append(tokens)

        self.bm25 = BM25Okapi(self.corpus_tokens)

    def search(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        scores = self.bm25.get_scores(query_tokens)
        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]

        results = []
        for idx in ranked_indices:
            chunk = self.chunks[idx]
            results.append({
                "chunk_id": chunk["chunk_id"],
                "citation": chunk["citation"],
                "score": float(scores[idx]),
            })
        return results


# Global singleton instance for module-level search
_searcher = None


def get_searcher() -> BM25Searcher:
    global _searcher
    if _searcher is None:
        _searcher = BM25Searcher()
    return _searcher


def search(query: str, k: int = 3) -> List[Dict[str, Any]]:
    return get_searcher().search(query, k=k)


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "minimum tension reinforcement in a beam"
    print(f"Query: {q}")
    for res in search(q, k=3):
        print(f"  [{res['score']:.4f}] {res['chunk_id']} ({res['citation']})")
