"""
Qdrant Vector Database Integration for Multi-Standard Structural IS Codes.

Step 5: Embedding & Vector Indexing
Supports:
- Domain-adapted embedding models:
  * BAAI/bge-small-en-v1.5 (default, 384-dimensional dense semantic embeddings)
  * intfloat/e5-small-v2 (384-dimensional dense semantic embeddings)
  * OpenAI text-embedding-3-large (via OpenAI client adapter, 384-dim projected)
- Qdrant Local Client (disk-backed embedded vector store, 100% offline, zero server daemon)
- Complete corpus indexed: IS 456, IS 13920, IS 1893, IS 800, IS 875 (Parts 1, 2, 3), official amendments, errata, and worked examples (1,535 chunks)
- Supports dense cosine similarity and native Qdrant metadata payload filtering.
"""

import atexit
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    MatchText,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
QDRANT_STORAGE_DIR = DATA_PROCESSED_DIR / "qdrant_storage"

COLLECTION_NAME = "structural_is_codes"
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
VECTOR_DIMENSION = 384


class EmbeddingAdapter:
    """
    Unified domain-adapted embedding adapter supporting BGE, E5, and OpenAI text-embedding-3-large.
    """
    def __init__(self, model_name: str = EMBEDDING_MODEL_NAME):
        self.model_name = model_name
        self._st_model: Optional[SentenceTransformer] = None

    def encode(self, texts: List[str], batch_size: int = 64) -> np.ndarray:
        if "text-embedding-3" in self.model_name.lower():
            try:
                from openai import OpenAI
                api_key = os.getenv("OPENAI_API_KEY")
                if api_key:
                    client = OpenAI(api_key=api_key)
                    all_embs = []
                    for i in range(0, len(texts), batch_size):
                        batch = texts[i : i + batch_size]
                        resp = client.embeddings.create(model=self.model_name, dimensions=VECTOR_DIMENSION, input=batch)
                        all_embs.extend([d.embedding for d in resp.data])
                    embs = np.array(all_embs, dtype=np.float32)
                    norms = np.linalg.norm(embs, axis=1, keepdims=True)
                    norms[norms == 0] = 1.0
                    return embs / norms
            except Exception as e:
                print(f"[EmbeddingAdapter] OpenAI embeddings unavailable ({e}); falling back to local BGE.")

        # Default local SentenceTransformer (BGE / E5)
        if self._st_model is None:
            model_target = self.model_name if "text-embedding-3" not in self.model_name.lower() else "BAAI/bge-small-en-v1.5"
            self._st_model = SentenceTransformer(model_target)
        embs = self._st_model.encode(texts, batch_size=batch_size, normalize_embeddings=True)
        return np.array(embs, dtype=np.float32)

    def encode_query(self, query: str) -> List[float]:
        if "bge" in self.model_name.lower():
            query_text = f"{QUERY_PREFIX}{query.strip()}"
        else:
            query_text = query.strip()
        embs = self.encode([query_text], batch_size=1)
        return embs[0].tolist()


def normalize_code_name(code_str: str) -> str:
    """Normalizes code identifier for clean standard-level filtering."""
    c = code_str.strip()
    if "/" in c:
        return c.split("/")[0].strip()
    return c


def load_all_structural_chunks() -> List[Dict[str, Any]]:
    """
    Consolidates chunks from all Indian standards into a unified payload list.
    Loads from all_enriched_chunks.jsonl (1,535 chunks) with fallback to legacy files.
    """
    unified_chunks: List[Dict[str, Any]] = []
    seen_ids = set()

    enriched_file = DATA_PROCESSED_DIR / "all_enriched_chunks.jsonl"
    if enriched_file.exists():
        with open(enriched_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                c = json.loads(line)
                cid = c.get("chunk_id")
                if cid and cid not in seen_ids:
                    seen_ids.add(cid)
                    raw_code = c.get("code", "")
                    clean_code = normalize_code_name(raw_code)
                    clause_str = str(c.get("clause_number") or "")
                    title_str = c.get("title", "")
                    citation_str = c.get("citation") or (f"{clean_code} Cl. {clause_str}" if clause_str else clean_code)
                    raw_text = c.get("text", "")
                    text_str = f"{title_str}: {raw_text}".strip() if title_str and not raw_text.startswith(title_str) else raw_text.strip()

                    unified_chunks.append({
                        "chunk_id": cid,
                        "code": clean_code,
                        "raw_code": raw_code,
                        "year": c.get("year", 2000),
                        "amendment": c.get("amendment"),
                        "section": c.get("section", ""),
                        "clause": clause_str,
                        "title": title_str,
                        "citation": citation_str,
                        "text": text_str,
                        "category": c.get("chunk_type", "clause"),
                        "applicability": c.get("applicability", ""),
                        "keywords": c.get("keywords", []),
                        "dependencies": c.get("dependencies", []),
                        "verified": c.get("verified", False),
                    })
        return unified_chunks

    # Legacy fallback (if all_enriched_chunks.jsonl is not present)
    chunks_file = DATA_PROCESSED_DIR / "chunks.jsonl"
    if chunks_file.exists():
        with open(chunks_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    c = json.loads(line)
                    cid = c.get("chunk_id")
                    if cid and cid not in seen_ids:
                        seen_ids.add(cid)
                        unified_chunks.append({
                            "chunk_id": cid,
                            "code": "IS 456:2000",
                            "clause": str(c.get("clause_number") or c.get("table_number") or ""),
                            "title": c.get("title", ""),
                            "citation": c.get("citation", f"IS 456:2000 Cl. {c.get('clause_number', '')}"),
                            "text": f"{c.get('title', '')}: {c.get('text', '')}".strip(),
                            "category": "core_concrete",
                        })

    def load_verified_code(file_path: Path, code_id: str, category: str):
        if not file_path.exists():
            return
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            for c in data.get("clauses", []):
                c_num = str(c.get("clause_number", ""))
                cid = f"{code_id.replace(' ', '-').replace(':', '-')}-CL-{c_num.replace(' ', '-')}"
                if cid not in seen_ids:
                    seen_ids.add(cid)
                    unified_chunks.append({
                        "chunk_id": cid,
                        "code": code_id,
                        "clause": c_num,
                        "title": c.get("title", ""),
                        "citation": c.get("citation", f"{code_id} Cl. {c_num}"),
                        "text": f"{c.get('title', '')}: {c.get('content', c.get('text', ''))}".strip(),
                        "category": category,
                    })

    load_verified_code(DATA_PROCESSED_DIR / "is13920_verified_clauses.json", "IS 13920:2016", "seismic_ductility")
    load_verified_code(DATA_PROCESSED_DIR / "is1893_verified_clauses.json", "IS 1893 (Part 1):2016", "earthquake_criteria")
    load_verified_code(DATA_PROCESSED_DIR / "is875_verified_clauses.json", "IS 875 (Part 2):1987", "imposed_loads")
    load_verified_code(DATA_PROCESSED_DIR / "is800_verified_clauses.json", "IS 800:2007", "structural_steel")

    return unified_chunks


class QdrantStructuralDB:
    """
    Embedded Qdrant Vector Database instance managing persistent vector collections
    and semantic search across Indian Standards.
    """

    def __init__(
        self,
        storage_path: Path = QDRANT_STORAGE_DIR,
        collection_name: str = COLLECTION_NAME,
        model_name: str = EMBEDDING_MODEL_NAME,
    ):
        self.storage_path = Path(storage_path)
        self.collection_name = collection_name
        self.model_name = model_name
        self.adapter = EmbeddingAdapter(model_name=self.model_name)

        self.storage_path.mkdir(parents=True, exist_ok=True)
        # Initialize local persistent Qdrant instance
        self.client = QdrantClient(path=str(self.storage_path))
        self._initialize_collection()
        chunks = load_all_structural_chunks()
        if self.count_points() != len(chunks):
            self.index_all_standards()
        atexit.register(self.close)

    def close(self) -> None:
        """Gracefully closes Qdrant local client locks."""
        if hasattr(self, "client") and self.client is not None:
            try:
                self.client.close()
            except Exception:
                pass

    def _initialize_collection(self) -> None:
        """Creates collection if it does not already exist."""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)

        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=VECTOR_DIMENSION, distance=Distance.COSINE),
            )

    def count_points(self) -> int:
        """Returns the number of indexed vectors in Qdrant."""
        try:
            info = self.client.get_collection(self.collection_name)
            return info.points_count or 0
        except Exception:
            return 0

    def index_all_standards(self, batch_size: int = 64, force_reindex: bool = False) -> int:
        """
        Embeds and upserts all chunks across the Indian Standards into Qdrant.
        """
        chunks = load_all_structural_chunks()
        if not chunks:
            return 0

        current_count = self.count_points()
        if current_count == len(chunks) and not force_reindex:
            return current_count

        print(f"[Qdrant] Indexing {len(chunks)} structural chunks (reindex={force_reindex}, current={current_count})...")

        # Clear existing points
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=VECTOR_DIMENSION, distance=Distance.COSINE),
        )

        texts_to_embed = [c["text"] for c in chunks]
        embeddings = self.adapter.encode(texts_to_embed, batch_size=batch_size)

        points = []
        for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            point = PointStruct(
                id=idx + 1,
                vector=emb.tolist(),
                payload=chunk,
            )
            points.append(point)

        # Upsert in batches into Qdrant
        print(f"[Qdrant] Upserting {len(points)} vectors into '{self.collection_name}'...")
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch,
            )

        new_count = self.count_points()
        print(f"[Qdrant] Successfully indexed {new_count} points in local Qdrant database.")
        return new_count

    def search(
        self,
        query: str,
        code_filter: Optional[str] = None,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Executes semantic dense retrieval over Qdrant with optional code filtering.
        """
        if not query.strip():
            return []

        query_vector = self.adapter.encode_query(query)

        # Build Qdrant metadata filter if code specified
        q_filter = None
        if code_filter:
            q_filter = Filter(
                must=[
                    FieldCondition(
                        key="code",
                        match=MatchText(text=code_filter),
                    )
                ]
            )

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=q_filter,
            limit=top_k,
            with_payload=True,
        )

        results = []
        for hit in response.points:
            payload = hit.payload or {}
            results.append({
                "chunk_id": payload.get("chunk_id"),
                "code": payload.get("code"),
                "year": payload.get("year"),
                "amendment": payload.get("amendment"),
                "section": payload.get("section"),
                "clause": payload.get("clause"),
                "title": payload.get("title"),
                "citation": payload.get("citation"),
                "text": payload.get("text"),
                "category": payload.get("category"),
                "applicability": payload.get("applicability"),
                "keywords": payload.get("keywords", []),
                "dependencies": payload.get("dependencies", []),
                "verified": payload.get("verified", False),
                "score": round(float(hit.score), 4),
            })

        return results


# Global singleton
_GLOBAL_QDRANT_DB: Optional[QdrantStructuralDB] = None


def get_qdrant_db() -> QdrantStructuralDB:
    global _GLOBAL_QDRANT_DB
    if _GLOBAL_QDRANT_DB is None:
        _GLOBAL_QDRANT_DB = QdrantStructuralDB()
    return _GLOBAL_QDRANT_DB
