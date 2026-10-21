"""
Unit tests for IS Code ClauseChunk schema and processed data.
"""

import json
from pathlib import Path
import pytest
from src.chunking.schema import ClauseChunk

DATA_PATH = Path("data/processed/is456_cl_26_5_1.json")


@pytest.fixture
def raw_records():
    assert DATA_PATH.exists(), f"Data file not found at {DATA_PATH}"
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def clause_chunks(raw_records):
    return [ClauseChunk(**r) for r in raw_records]


def test_validate_all_records(clause_chunks):
    """Checks that every record in the JSON parses cleanly into ClauseChunk."""
    assert len(clause_chunks) > 0
    for chunk in clause_chunks:
        assert isinstance(chunk, ClauseChunk)
        assert chunk.code_id == "IS 456"
        assert chunk.edition_year == 2000
        # Ensure raw_text is never returned in embedding_text
        assert chunk.raw_text not in chunk.embedding_text


def test_nine_unique_clauses(clause_chunks):
    """Checks that there are exactly 9 records and every clause_number is unique."""
    assert len(clause_chunks) == 9, f"Expected 9 records, got {len(clause_chunks)}"
    clause_numbers = [c.clause_number for c in clause_chunks]
    unique_clause_numbers = set(clause_numbers)
    assert len(unique_clause_numbers) == 9, (
        f"Duplicate clause numbers found: {clause_numbers}"
    )


def test_no_unverified_or_ocr_in_any_embedding_text(clause_chunks):
    """
    Checks ALL records to ensure embedding_text contains neither
    'UNVERIFIED' nor 'OCR:'.
    """
    problematic = {}
    for chunk in clause_chunks:
        emb = chunk.embedding_text
        reasons = []
        if "UNVERIFIED" in emb:
            reasons.append("Contains 'UNVERIFIED'")
        if "OCR:" in emb:
            reasons.append("Contains 'OCR:'")
        if reasons:
            problematic[chunk.clause_number] = reasons

    assert not problematic, f"Found unverified/OCR artifacts in embedding_text: {problematic}"
