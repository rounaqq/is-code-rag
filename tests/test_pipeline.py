"""
Tests for unified retrieval pipeline (src/retrieval/pipeline.py).
Validates top retrieval precision, metadata completeness, and graceful error handling.
"""

from src.retrieval.pipeline import retrieve


def test_retrieve_table_16_top_hit():
    """retrieve('nominal cover for moderate exposure')[0] is IS456-2000-TABLE-16."""
    results = retrieve("nominal cover for moderate exposure", k=3)
    assert len(results) > 0
    assert results[0]["chunk_id"] == "IS456-2000-TABLE-16"


def test_returned_items_citation_and_verified():
    """Every returned item has a non-empty citation and verified true."""
    test_queries = [
        "nominal cover for moderate exposure",
        "maximum tension reinforcement in a beam",
        "design shear strength of concrete M25",
    ]
    for q in test_queries:
        results = retrieve(q, k=3)
        assert len(results) > 0
        for item in results:
            assert item.get("citation") and len(item["citation"].strip()) > 0, (
                f"Missing or empty citation in chunk {item.get('chunk_id')}"
            )
            assert item.get("verified") is True, (
                f"Item {item.get('chunk_id')} not verified"
            )


def test_nonsense_query_returns_list():
    """The query 'xyz nonsense' still returns a list without error."""
    results = retrieve("xyz nonsense", k=3)
    assert isinstance(results, list)
