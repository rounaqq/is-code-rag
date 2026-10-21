"""
Tests for deterministic IS 456 beam design validation (src/generation/design_validation.py).
No LLM calls or network requests. Does NOT read .env.
"""

import pytest
from src.generation.design_validation import validate_design, CITATION_TO_CHUNK_ID, get_chunks_map


VALID_DESIGN = {
    "b": 300,
    "D": 500,
    "d": 450,
    "fck": 25,
    "fy": 500,
    "exposure": "Moderate",
    "main_bar_dia_mm": 20,
    "main_bar_count": 4,
    "stirrup_dia_mm": 8,
    "stirrup_spacing_mm": 150,
}


def test_valid_design_passed_with_cover_and_clause_text():
    """
    A design with 4 bars of 20 mm, stirrups 8 mm at 150 mm for
    b=300, D=500, d=450, fy=500, Moderate exposure gives a result
    with cover 30 and every check carrying a clause text.
    """
    res = validate_design(VALID_DESIGN)

    assert res["status"] == "passed"
    assert res["cover_mm"] == 30
    assert len(res["checks"]) > 0

    # Ensure every check carries chunk_id, citation, and non-empty clause text
    for c in res["checks"]:
        assert c["passed"] is True
        assert "chunk_id" in c and len(c["chunk_id"]) > 0
        assert "citation" in c and len(c["citation"]) > 0
        assert "clause_text" in c and len(c["clause_text"]) > 0

    expected_note = (
        "Passes the implemented IS 456 beam detailing checks only; "
        "not a full design check. A structural engineer must review."
    )
    assert res["notes"] == expected_note
    assert res["design"] == VALID_DESIGN


def test_stirrup_spacing_400_fails_spacing_check():
    """A design with stirrup spacing 400 fails the spacing check."""
    design_spacing_400 = dict(VALID_DESIGN, stirrup_spacing_mm=400)
    res = validate_design(design_spacing_400)

    assert res["status"] == "failed"

    # Verify spacing check failed specifically
    spacing_check = next((c for c in res["checks"] if c["check"] == "max_stirrup_spacing"), None)
    assert spacing_check is not None
    assert spacing_check["passed"] is False
    assert spacing_check["required"] == 300.0
    assert spacing_check["provided"] == 400.0
    assert "clause_text" in spacing_check and len(spacing_check["clause_text"]) > 0
    assert spacing_check["chunk_id"] == "IS456-2000-CL-26.5.1.5"


def test_unknown_exposure_raises_value_error():
    """Unknown exposure raises ValueError."""
    design_bad_exposure = dict(VALID_DESIGN, exposure="ExtremeGlacierCondition")
    with pytest.raises(ValueError) as exc_info:
        validate_design(design_bad_exposure)

    assert "Unknown exposure" in str(exc_info.value) or "exposure" in str(exc_info.value).lower()


def test_design_with_compression_steel_validated():
    """Design with optional compression steel runs max_compression_steel check."""
    design_with_comp = dict(
        VALID_DESIGN,
        compression_bar_dia_mm=12,
        compression_bar_count=2,
    )
    res = validate_design(design_with_comp)

    assert res["status"] == "passed"
    comp_check = next((c for c in res["checks"] if c["check"] == "max_compression_steel"), None)
    assert comp_check is not None
    assert comp_check["passed"] is True
    assert comp_check["chunk_id"] == "IS456-2000-CL-26.5.1.2"
    assert "clause_text" in comp_check and len(comp_check["clause_text"]) > 0


def test_missing_required_parameter_raises_value_error():
    """Missing required design parameter raises ValueError."""
    incomplete_design = dict(VALID_DESIGN)
    del incomplete_design["main_bar_count"]

    with pytest.raises(ValueError) as exc_info:
        validate_design(incomplete_design)

    assert "main_bar_count" in str(exc_info.value)


def test_citation_mapping_covers_all_checks():
    """Verifies that all citations produced by checks have valid mappings and clause text in chunks.jsonl."""
    chunks_map = get_chunks_map()
    for citation, chunk_id in CITATION_TO_CHUNK_ID.items():
        assert chunk_id in chunks_map, f"Chunk ID {chunk_id} for citation '{citation}' not in chunks.jsonl"
        assert len(chunks_map[chunk_id]) > 0
