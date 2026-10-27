"""
Unit tests for Multi-Standard IS Code Retrieval Engine.
Tests multi-code indexing across IS 456, IS 13920, and IS 875, filtering, and retrieval accuracy.
"""

from src.retrieval.multicode_search import retrieve_multicode, get_multicode_retriever


def test_multicode_corpus_loads_all_codes():
    """Retriever indexes chunks from IS 456, IS 13920, IS 875, IS 1893, and IS 800."""
    retriever = get_multicode_retriever()
    codes = {item["code"] for item in retriever.corpus}
    assert "IS 456:2000" in codes
    assert "IS 13920:2016" in codes
    assert "IS 875 (Part 2):1987" in codes
    assert "IS 1893 (Part 1):2016" in codes
    assert "IS 800:2007" in codes
    assert len(retriever.corpus) >= 50


def test_retrieve_is13920_seismic_confinement():
    """Retrieves IS 13920 Clause 6.3.3 for plastic hinge confining stirrup query."""
    results = retrieve_multicode(
        query="closely spaced confining stirrups plastic hinge zone 100 mm",
        code_filter="IS 13920",
        top_k=3,
    )
    assert len(results) > 0
    top_hit = results[0]
    assert "13920" in top_hit["code"]
    assert "6.3.3" in top_hit["clause"] or "6.3.1" in top_hit["clause"]


def test_retrieve_is875_classroom_live_load():
    """Retrieves IS 875 Table 1 for school classroom imposed load query."""
    results = retrieve_multicode(
        query="imposed live load school classrooms educational buildings",
        code_filter="IS 875",
        top_k=3,
    )
    assert len(results) > 0
    top_hit = results[0]
    assert "875" in top_hit["code"]
    assert "Educational" in top_hit["title"]
    assert "3.0 kN/m2" in top_hit["text"]


def test_retrieve_is456_minimum_cover():
    """Retrieves IS 456 Table 16 for concrete nominal cover query."""
    results = retrieve_multicode(
        query="nominal cover durability table 16",
        code_filter="IS 456",
        top_k=3,
    )
    assert len(results) > 0
    top_hit = results[0]
    assert "16" in top_hit["clause"] or "Table 16" in top_hit["citation"]



def test_code_filter_restricts_results():
    """Filtering by standard ensures only clauses from that standard are returned."""
    results = retrieve_multicode(
        query="reinforcement steel",
        code_filter="IS 13920",
        top_k=5,
    )
    for r in results:
        assert r["code"] == "IS 13920:2016"


def test_retrieve_is1893_zone_factors():
    """Retrieves IS 1893 Table 2 for seismic zone factor query."""
    results = retrieve_multicode(
        query="seismic zone factors zone iv zone v maximum considered earthquake",
        code_filter="IS 1893",
        top_k=3,
    )
    assert len(results) > 0
    top_hit = results[0]
    assert "1893" in top_hit["code"]
    assert "Zone Factor" in top_hit["title"] or "6.4.2" in top_hit["clause"] or "Table 2" in top_hit["clause"]


def test_retrieve_is800_slenderness_limits():
    """Retrieves IS 800 Table 3 for steel maximum slenderness ratio query."""
    results = retrieve_multicode(
        query="maximum slenderness ratio kl r compression member dead load",
        code_filter="IS 800",
        top_k=3,
    )
    assert len(results) > 0
    top_hit = results[0]
    assert "800" in top_hit["code"]
    assert "Slenderness" in top_hit["title"] or "Table 3" in top_hit["clause"]
