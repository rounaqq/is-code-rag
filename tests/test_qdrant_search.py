"""
Unit tests for Qdrant Vector Database Dense Semantic Retrieval.

Step 5: Embedding & Vector Indexing
Step 6: Retrieval System

Verifies:
- Embedded Qdrant database contains all indexed points (>900 structural chunks).
- Dense semantic search using BGE-small embeddings.
- Precise clause matching for IS 13920, IS 1893, IS 875, IS 800, and IS 456.
- Metadata payload code filtering (restricting to specific standards).
"""

from src.retrieval.qdrant_db import get_qdrant_db


def test_qdrant_points_count():
    """Qdrant contains all vectorized points across the 5 structural standards."""
    db = get_qdrant_db()
    count = db.count_points()
    assert count >= 900, f"Expected >= 900 indexed points in Qdrant, got {count}"


def test_qdrant_seismic_confinement_retrieval():
    """Dense semantic search retrieves IS 13920 confining stirrup clauses."""
    db = get_qdrant_db()
    results = db.search(
        query="closely spaced confining stirrups plastic hinge zone 100 mm spacing",
        code_filter="13920",
        top_k=3,
    )
    assert len(results) > 0
    top = results[0]
    assert "13920" in top["code"]
    assert any("6.3" in r["clause"] or "confinement" in r["text"].lower() or "stirrup" in r["text"].lower() for r in results)
    assert top["score"] > 0.60


def test_qdrant_seismic_base_shear_retrieval():
    """Dense semantic search retrieves IS 1893 base shear distribution clauses."""
    db = get_qdrant_db()
    results = db.search(
        query="equivalent static lateral base shear vertical distribution to floors",
        code_filter="1893",
        top_k=3,
    )
    assert len(results) > 0
    top = results[0]
    assert "1893" in top["code"]
    assert any("shear" in r["text"].lower() or "distribution" in r["text"].lower() or "7.6" in r["clause"] for r in results)
    assert top["score"] > 0.60


def test_qdrant_imposed_load_retrieval():
    """Dense semantic search retrieves IS 875 occupancy imposed loads."""
    db = get_qdrant_db()
    results = db.search(
        query="imposed live load classroom educational buildings school",
        code_filter="875",
        top_k=3,
    )
    assert len(results) > 0
    top = results[0]
    assert "875" in top["code"]
    assert any("educational" in r["text"].lower() or "3.0" in r["text"] or "classroom" in r["text"].lower() for r in results)


def test_qdrant_steel_slenderness_retrieval():
    """Dense semantic search retrieves IS 800 steel slenderness ratio limits."""
    db = get_qdrant_db()
    results = db.search(
        query="maximum effective slenderness ratio compression members struts",
        code_filter="800",
        top_k=3,
    )
    assert len(results) > 0
    top = results[0]
    assert "800" in top["code"]
    assert any("slenderness" in r["text"].lower() or "table 3" in r["citation"].lower() or "compression" in r["text"].lower() for r in results)


def test_qdrant_code_filtering():
    """Payload code filter strictly restricts results to the target standard."""
    db = get_qdrant_db()
    results = db.search(
        query="minimum clear concrete cover durability requirement",
        code_filter="IS 456",
        top_k=5,
    )
    assert len(results) > 0
    for r in results:
        assert "456" in r["code"]
