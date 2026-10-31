"""
Step 5 Verification Suite: Embedding & Vector Indexing.

Validates:
1. Domain-adapted embedding models (BGE, E5, OpenAI adapter).
2. Embedded vector store (Qdrant) indexing all 1,535 multi-standard chunks.
3. Complete metadata enrichment in vector payload (code, year, amendment, section, clause, applicability, keywords, dependencies).
4. BM25 index built over the full 1,535 structural chunks.
5. Dense vector retrieval precision, confidence scores, and payload filtering.
"""

import numpy as np
import pytest
from src.retrieval.qdrant_db import (
    EmbeddingAdapter,
    QdrantStructuralDB,
    get_qdrant_db,
    load_all_structural_chunks,
    VECTOR_DIMENSION,
)
from src.retrieval.multicode_search import get_multicode_retriever


def test_embedding_adapter_bge_encoding_dimension_and_normalization():
    """EmbeddingAdapter generates normalized 384-dimensional embeddings using BGE."""
    adapter = EmbeddingAdapter(model_name="BAAI/bge-small-en-v1.5")
    texts = [
        "Minimum reinforcement in reinforced concrete flexural members as per IS 456.",
        "Special confining reinforcement for ductile detailing of columns under IS 13920.",
    ]
    embs = adapter.encode(texts, batch_size=2)
    assert isinstance(embs, np.ndarray)
    assert embs.shape == (2, VECTOR_DIMENSION)
    # Norms should be approximately 1.0 (normalized cosine distance)
    norms = np.linalg.norm(embs, axis=1)
    for norm in norms:
        assert np.isclose(norm, 1.0, atol=1e-3)


def test_embedding_adapter_query_encoding():
    """Query encoding applies proper prefix and returns a float vector."""
    adapter = EmbeddingAdapter()
    query_vec = adapter.encode_query("lateral drift in multi-storey buildings IS 1893")
    assert isinstance(query_vec, list)
    assert len(query_vec) == VECTOR_DIMENSION
    assert all(isinstance(v, float) for v in query_vec)


def test_embedding_adapter_openai_graceful_fallback():
    """OpenAI adapter gracefully handles missing API key and falls back cleanly."""
    adapter = EmbeddingAdapter(model_name="text-embedding-3-large")
    vec = adapter.encode_query("wind pressure coefficients IS 875 Part 3")
    assert len(vec) == VECTOR_DIMENSION


def test_qdrant_vector_store_contains_complete_corpus():
    """Qdrant contains all indexed chunks across all standards."""
    db = get_qdrant_db()
    chunks = load_all_structural_chunks()
    assert len(chunks) >= 1535
    assert db.count_points() == len(chunks)


def test_qdrant_payload_contains_all_metadata_fields():
    """Vector payload stores rich metadata for downstream CAD citation and auditability."""
    db = get_qdrant_db()
    results = db.search("maximum reinforcement in beam", top_k=1)
    assert len(results) > 0
    hit = results[0]
    required_keys = [
        "chunk_id", "code", "year", "amendment", "section",
        "clause", "title", "citation", "text", "category",
        "applicability", "keywords", "dependencies", "verified", "score",
    ]
    for key in required_keys:
        assert key in hit, f"Missing required payload key: {key}"


def test_bm25_multi_standard_index_covers_all_chunks():
    """BM25 index covers all multi-standard chunks."""
    retriever = get_multicode_retriever()
    assert len(retriever.corpus) == len(load_all_structural_chunks())
    assert len(retriever.corpus) >= 1535
    assert retriever.bm25 is not None


def test_dense_semantic_search_confidence_and_filtering():
    """Qdrant dense vector search returns high confidence results with standard filtering."""
    db = get_qdrant_db()
    # Query IS 1893 seismic base shear
    hits = db.search("design lateral force seismic base shear distribution", code_filter="IS 1893", top_k=3)
    assert len(hits) > 0
    for h in hits:
        assert "1893" in h["code"]
        assert h["score"] > 0.50
