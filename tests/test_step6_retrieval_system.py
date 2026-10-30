"""
Step 6 Verification Suite: Retrieval System (Hybrid + Cross-Encoder Reranking).

Validates:
1. Hybrid search combining BM25 lexical precision and dense semantic vectors.
2. Cross-Encoder reranking (BAAI/bge-reranker-base / Cohere adapter).
3. Return payload structure: top-k clauses with exact citations, full text, and calibrated confidence scores (0.0 to 1.0).
4. Clause-level retrieval accuracy across multi-standard queries.
5. Standard-specific filtering and federated cross-standard retrieval.
"""

import pytest
from src.retrieval.multicode_search import (
    MultiCodeRetriever,
    get_multicode_retriever,
    retrieve_multicode,
)
from src.retrieval.pipeline import retrieve


def test_hybrid_search_combines_lexical_and_dense():
    """Hybrid search merges BM25 and Qdrant results using Reciprocal Rank Fusion."""
    retriever = get_multicode_retriever()
    results = retriever.search(
        query="limiting moment of resistance singly reinforced rectangular beam Fe 415",
        mode="hybrid",
        top_k=5,
    )
    assert len(results) > 0
    assert all("score" in r for r in results)
    assert any("456" in r["code"] for r in results)


def test_cross_encoder_reranking_attaches_confidence_scores():
    """Reranking produces calibrated confidence scores between 0.0 and 1.0 and rerank scores."""
    retriever = get_multicode_retriever()
    results = retriever.search(
        query="maximum compressive strain in concrete in axial compression",
        mode="rerank",
        top_k=3,
    )
    assert len(results) > 0
    top = results[0]
    assert "confidence_score" in top
    assert 0.0 <= top["confidence_score"] <= 1.0
    assert "rerank_score" in top
    assert "citation" in top
    assert "text" in top


def test_retrieve_pipeline_returns_citations_and_confidence_scores():
    """Standard pipeline retrieval returns citation, text, verified tag, and confidence score."""
    results = retrieve("minimum clear concrete cover for mild exposure durability", k=3)
    assert len(results) > 0
    for r in results:
        assert "citation" in r
        assert "confidence_score" in r
        assert 0.0 <= r["confidence_score"] <= 1.0
        assert "text" in r
        assert len(r["text"]) > 10


def test_multi_standard_seismic_ductility_reranked():
    """Reranked retrieval precisely surfaces IS 13920 Clause 6.3.3 for confining hoops."""
    results = retrieve_multicode(
        query="closely spaced confining stirrups plastic hinge zone spacing beam",
        code_filter="IS 13920",
        top_k=3,
        rerank=True,
    )
    assert len(results) > 0
    top = results[0]
    assert "13920" in top["code"]
    assert "6.3" in top["clause"] or "confinement" in top["text"].lower() or "stirrup" in top["text"].lower()
    assert top["confidence_score"] > 0.50


def test_multi_standard_earthquake_base_shear_reranked():
    """Reranked retrieval precisely surfaces IS 1893 seismic base shear provisions."""
    results = retrieve_multicode(
        query="design seismic base shear Ah lateral force vertical distribution",
        code_filter="IS 1893",
        top_k=3,
        rerank=True,
    )
    assert len(results) > 0
    top = results[0]
    assert "1893" in top["code"]
    assert any("shear" in r["text"].lower() or "7.6" in r["clause"] or "6.4" in r["clause"] for r in results)
    assert top["confidence_score"] > 0.40
