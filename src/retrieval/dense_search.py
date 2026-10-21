"""
Dense (Embedding-based) Retrieval over IS Code Chunks using BAAI/bge-small-en-v1.5.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
from sentence_transformers import SentenceTransformer

CHUNKS_PATH = Path("data/processed/chunks.jsonl")
EMBEDDINGS_PATH = Path("data/processed/embeddings.npy")
EMBEDDING_IDS_PATH = Path("data/processed/embedding_ids.json")
MODEL_NAME = "BAAI/bge-small-en-v1.5"
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def build_and_save_embeddings(
    chunks_path: Path = CHUNKS_PATH,
    embeddings_path: Path = EMBEDDINGS_PATH,
    ids_path: Path = EMBEDDING_IDS_PATH,
    model_name: str = MODEL_NAME,
) -> np.ndarray:
    """
    Loads chunks from chunks.jsonl, embeds context_path + title + text using
    BAAI/bge-small-en-v1.5 (with normalization), and saves embeddings.npy and embedding_ids.json.
    """
    if not chunks_path.exists():
        raise FileNotFoundError(f"Chunks file not found at {chunks_path}")

    chunks = []
    with open(chunks_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                chunks.append(json.loads(line.strip()))

    texts = []
    chunk_ids = []
    for chunk in chunks:
        context = chunk.get("context_path") or ""
        title = chunk.get("title") or ""
        text = chunk.get("text") or ""
        combined_text = f"{context} {title} {text}".strip()
        texts.append(combined_text)
        chunk_ids.append(chunk["chunk_id"])

    print(f"Loading embedding model: {model_name}...")
    model = SentenceTransformer(model_name)

    print(f"Generating normalized embeddings for {len(texts)} chunks...")
    embeddings = model.encode(texts, normalize_embeddings=True)
    embeddings = np.array(embeddings, dtype=np.float32)

    embeddings_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(embeddings_path, embeddings)
    with open(ids_path, "w", encoding="utf-8") as f:
        json.dump(chunk_ids, f, indent=2, ensure_ascii=False)

    print(f"Saved {embeddings.shape[0]} embeddings to {embeddings_path}")
    print(f"Saved {len(chunk_ids)} chunk IDs to {ids_path}")
    return embeddings


class DenseSearcher:
    def __init__(
        self,
        chunks_path: Path = CHUNKS_PATH,
        embeddings_path: Path = EMBEDDINGS_PATH,
        ids_path: Path = EMBEDDING_IDS_PATH,
        model_name: str = MODEL_NAME,
    ):
        self.chunks_path = Path(chunks_path)
        self.embeddings_path = Path(embeddings_path)
        self.ids_path = Path(ids_path)
        self.model_name = model_name
        self.model: Optional[SentenceTransformer] = None
        self.chunk_by_id: Dict[str, Dict[str, Any]] = {}
        self.chunk_ids: List[str] = []
        self.embeddings: Optional[np.ndarray] = None

        self._load_data()

    def _load_data(self) -> None:
        if not self.chunks_path.exists():
            raise FileNotFoundError(f"Chunks file not found at {self.chunks_path}")

        # Load chunks for citation metadata
        with open(self.chunks_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    chunk = json.loads(line.strip())
                    self.chunk_by_id[chunk["chunk_id"]] = chunk

        # Build or load embeddings
        if not self.embeddings_path.exists() or not self.ids_path.exists():
            print("Embeddings or ID file not found. Generating now...")
            self.embeddings = build_and_save_embeddings(
                chunks_path=self.chunks_path,
                embeddings_path=self.embeddings_path,
                ids_path=self.ids_path,
                model_name=self.model_name,
            )
            with open(self.ids_path, "r", encoding="utf-8") as f:
                self.chunk_ids = json.load(f)
        else:
            self.embeddings = np.load(self.embeddings_path)
            with open(self.ids_path, "r", encoding="utf-8") as f:
                self.chunk_ids = json.load(f)

        self.model = SentenceTransformer(self.model_name)

    def search(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        if not query.strip():
            return []

        # Model card query instruction prefix
        prefixed_query = f"{QUERY_PREFIX}{query.strip()}"
        query_embedding = self.model.encode(prefixed_query, normalize_embeddings=True)
        query_embedding = np.array(query_embedding, dtype=np.float32)

        # Cosine similarity for normalized vectors is the dot product
        scores = np.dot(self.embeddings, query_embedding)
        ranked_indices = np.argsort(scores)[::-1][:k]

        results = []
        for idx in ranked_indices:
            cid = self.chunk_ids[idx]
            chunk = self.chunk_by_id.get(cid, {})
            results.append({
                "chunk_id": cid,
                "citation": chunk.get("citation", cid),
                "score": float(scores[idx]),
            })
        return results


# Module-level singleton
_dense_searcher: Optional[DenseSearcher] = None


def get_searcher() -> DenseSearcher:
    global _dense_searcher
    if _dense_searcher is None:
        _dense_searcher = DenseSearcher()
    return _dense_searcher


def search(query: str, k: int = 3) -> List[Dict[str, Any]]:
    return get_searcher().search(query, k=k)


if __name__ == "__main__":
    import sys
    # Rebuild embeddings if --rebuild flag is passed
    if "--rebuild" in sys.argv:
        build_and_save_embeddings()
    else:
        q = " ".join([arg for arg in sys.argv[1:] if not arg.startswith("--")])
        if not q:
            q = "maximum tension reinforcement in a beam"
        print(f"Query: {q}")
        for res in search(q, k=3):
            print(f"  [{res['score']:.4f}] {res['chunk_id']} ({res['citation']})")
