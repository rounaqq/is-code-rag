"""
Qdrant Vector Database Integration for Multi-Standard Structural IS Codes.

Step 5: Embedding & Vector Indexing
Uses:
- BAAI/bge-small-en-v1.5 (384-dimensional dense semantic embeddings)
- Qdrant Local Client (disk-backed embedded vector store, 100% offline, zero server daemon)
- Indexed Codes: IS 456:2000, IS 13920:2016, IS 1893 (Part 1):2016, IS 875 (Part 2):1987, IS 800:2007
- Supports dense cosine similarity and native Qdrant metadata payload filtering.
"""

import atexit
import json
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
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
VECTOR_DIMENSION = 384


def load_all_structural_chunks() -> List[Dict[str, Any]]:
    """
    Consolidates chunks from all 5 Indian standards into a unified payload list.
    """
    unified_chunks: List[Dict[str, Any]] = []
    seen_ids = set()

    # 1. IS 456:2000 Chunks
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

    # Helper for verified JSON standards
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

    # Helper for preprocessed OCR documents
    def load_preprocessed_code(file_path: Path, category: str):
        if not file_path.exists():
            return
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            code_id = data.get("code", "")
            for c in data.get("chunks", []):
                cid = c.get("chunk_id")
                if cid and cid not in seen_ids:
                    seen_ids.add(cid)
                    unified_chunks.append({
                        "chunk_id": cid,
                        "code": code_id,
                        "clause": str(c.get("clause_number", "")),
                        "title": c.get("title", ""),
                        "citation": f"{code_id} Cl. {c.get('clause_number', '')}",
                        "text": c.get("text", "").strip(),
                        "category": category,
                    })

    # 2. IS 13920 (Seismic Ductile)
    load_verified_code(DATA_PROCESSED_DIR / "is13920_verified_clauses.json", "IS 13920:2016", "seismic_ductility")
    load_preprocessed_code(DATA_PROCESSED_DIR / "is13920_preprocessed.json", "seismic_ductility")

    # 3. IS 1893 (Earthquake Criteria)
    load_verified_code(DATA_PROCESSED_DIR / "is1893_verified_clauses.json", "IS 1893 (Part 1):2016", "earthquake_criteria")
    load_preprocessed_code(DATA_PROCESSED_DIR / "is1893_part_1_preprocessed.json", "earthquake_criteria")

    # 4. IS 875 (Imposed Loads)
    load_verified_code(DATA_PROCESSED_DIR / "is875_verified_clauses.json", "IS 875 (Part 2):1987", "imposed_loads")
    load_preprocessed_code(DATA_PROCESSED_DIR / "is875_part_2_preprocessed.json", "imposed_loads")

    # 5. IS 800 (Structural Steel)
    load_verified_code(DATA_PROCESSED_DIR / "is800_verified_clauses.json", "IS 800:2007", "structural_steel")
    load_preprocessed_code(DATA_PROCESSED_DIR / "is800_preprocessed.json", "structural_steel")

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
        self.model: Optional[SentenceTransformer] = None

        self.storage_path.mkdir(parents=True, exist_ok=True)
        # Initialize local persistent Qdrant instance
        self.client = QdrantClient(path=str(self.storage_path))
        self._initialize_collection()
        if self.count_points() == 0:
            self.index_all_standards()
        atexit.register(self.close)

    def close(self) -> None:
        """Gracefully closes Qdrant local client locks."""
        if hasattr(self, "client") and self.client is not None:
            try:
                self.client.close()
            except Exception:
                pass

    def _get_embedding_model(self) -> SentenceTransformer:
        if self.model is None:
            self.model = SentenceTransformer(self.model_name)
        return self.model

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
        info = self.client.get_collection(self.collection_name)
        return info.points_count or 0

    def index_all_standards(self, batch_size: int = 64, force_reindex: bool = False) -> int:
        """
        Embeds and upserts all chunks across the 5 Indian Standards into Qdrant.
        """
        current_count = self.count_points()
        if current_count > 100 and not force_reindex:
            return current_count

        chunks = load_all_structural_chunks()
        if not chunks:
            return 0

        model = self._get_embedding_model()
        texts_to_embed = [c["text"] for c in chunks]

        print(f"[Qdrant] Generating BGE embeddings for {len(chunks)} structural chunks...")
        embeddings = model.encode(texts_to_embed, batch_size=batch_size, normalize_embeddings=True)
        embeddings = np.array(embeddings, dtype=np.float32)

        points = []
        for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            point = PointStruct(
                id=idx + 1,
                vector=emb.tolist(),
                payload=chunk,
            )
            points.append(point)

        # Upsert in batches into Qdrant
        print(f"[Qdrant] Indexing {len(points)} vectors into '{self.collection_name}'...")
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

        model = self._get_embedding_model()
        query_text = f"{QUERY_PREFIX}{query.strip()}"
        query_vector = model.encode(query_text, normalize_embeddings=True).tolist()

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
                "clause": payload.get("clause"),
                "title": payload.get("title"),
                "citation": payload.get("citation"),
                "text": payload.get("text"),
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
