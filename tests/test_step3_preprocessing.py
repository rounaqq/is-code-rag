"""
Unit and integration tests for Step 3: Document Preprocessing.

Verifies:
- Layout-aware extraction across official BIS Amendments, Errata, and Supplementary Design Examples.
- IS 456 Full Standard preprocessing (359 clauses across all 114 pages).
- IS 875 Parts 1 and 3 preprocessing.
- Extraction of text, tables, figures, equations, and cross-references.
- Text normalization, clause numbering preservation, and hierarchy.
"""

import json
from pathlib import Path
import pytest

from src.ingestion.layout_preprocessor import (
    clean_text_formatting,
    extract_cross_references,
    extract_equations_from_text,
    is_table_block,
    parse_amendment_document,
    parse_errata_document,
    parse_design_example_document,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"


def test_text_cleaning_and_normalization():
    """Step 3: Text cleaning normalizes whitespace and removes page header noise."""
    raw = "  IS 456 : 2000 \n\n  BUREAU OF INDIAN STANDARDS\nClause 26.5.1   Beams \n  \n 47 \n Minimum steel."
    cleaned = clean_text_formatting(raw)
    assert "IS 456" not in cleaned
    assert "BUREAU OF INDIAN STANDARDS" not in cleaned
    assert "47" not in cleaned.splitlines()
    assert "Clause 26.5.1 Beams" in cleaned
    assert "Minimum steel." in cleaned


def test_cross_reference_extraction():
    """Step 3: Regex extractor identifies standards, clauses, tables, and annexes."""
    sample = (
        "As per IS 456:2000 Cl. 26.5.1.1(a) and Table 16, nominal cover shall be verified. "
        "For ductile detailing in seismic zones, refer to IS 13920:2016 Cl. 6.3.3 and Fig. 2. "
        "Moment capacity is computed using Annex G-1.1."
    )
    refs = extract_cross_references(sample)
    assert any("IS 456:2000" in r for r in refs)
    assert any("Cl. 26.5.1.1(a)" in r or "26.5.1.1" in r for r in refs)
    assert any("Table 16" in r for r in refs)
    assert any("IS 13920:2016" in r for r in refs)
    assert any("Annex G-1.1" in r for r in refs)


def test_equation_extraction_heuristics():
    """Step 3: Identifies equations with variables, operands, and numbers; rejects pure prose."""
    assert len(extract_equations_from_text("Mu = 0.87 * fy * Ast * d * (1 - Ast*fy/(b*d*fck))")) > 0
    assert len(extract_equations_from_text("Ta = 0.075 * h^0.75")) > 0
    assert len(extract_equations_from_text("VB = Ah * W")) > 0
    assert len(extract_equations_from_text("This is purely descriptive narrative text with no formulas.")) == 0


def test_table_block_detection():
    """Step 3: Distinguishes tabular numerical blocks from narrative paragraphs."""
    table_sample = "Table 16 Nominal Cover\nExposure | Cover mm\nMild | 20\nModerate | 30\nSevere | 45"
    assert is_table_block(table_sample) is True
    assert is_table_block("This is standard text describing beam reinforcement.") is False


def test_amendments_preprocessed_file_integrity():
    """Step 3: Verifies all 13 official BIS amendments are preprocessed with 59 chunks."""
    amd_file = DATA_PROCESSED_DIR / "amendments_preprocessed.json"
    assert amd_file.exists(), "amendments_preprocessed.json must exist"

    with open(amd_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("total_amendments") == 13
    assert data.get("total_chunks") == 59

    chunks = data.get("all_chunks", [])
    assert len(chunks) == 59

    # Verify chunk structure
    for c in chunks:
        assert "chunk_id" in c
        assert "code" in c
        assert "standard_code" in c
        assert "amendment_number" in c
        assert "clause_number" in c
        assert "title" in c
        assert "content" in c
        assert "cross_references" in c
        assert "equations" in c

    # Verify critical amendments coverage
    codes = {c["standard_code"] for c in chunks}
    assert "IS 456:2000" in codes
    assert "IS 13920:2016" in codes
    assert "IS 1893 (Part 1):2016" in codes
    assert "IS 800:2007" in codes
    assert "IS 875 (Part 3):2015" in codes


def test_errata_preprocessed_file_integrity():
    """Step 3: Verifies both official BIS errata documents are preprocessed."""
    err_file = DATA_PROCESSED_DIR / "errata_preprocessed.json"
    assert err_file.exists(), "errata_preprocessed.json must exist"

    with open(err_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("total_errata") == 2
    assert data.get("total_chunks") == 7

    chunks = data.get("all_chunks", [])
    assert len(chunks) == 7

    for c in chunks:
        assert "chunk_id" in c
        assert "errata_number" in c
        assert "content" in c
        assert len(c["content"]) > 10


def test_design_examples_preprocessed_file_integrity():
    """Step 3: Verifies supplementary worked design examples (IITK-GSDMA & SP:16) are preprocessed."""
    ex_file = DATA_PROCESSED_DIR / "design_examples_preprocessed.json"
    assert ex_file.exists(), "design_examples_preprocessed.json must exist"

    with open(ex_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("total_documents") == 3
    assert data.get("total_chunks") == 13

    chunks = data.get("all_chunks", [])
    codes = {c["code"] for c in chunks}
    assert "IITK-GSDMA EQ26" in codes
    assert "IITK-GSDMA EQ06" in codes
    assert "SP:16 Worked Examples" in codes

    for c in chunks:
        assert c.get("is_calculation") is True
        assert "title" in c
        assert "content" in c


def test_is456_full_preprocessed_file_integrity():
    """Step 3: Verifies IS 456:2000 full standard preprocessing covers over 350 clauses across 114 pages."""
    is456_file = DATA_PROCESSED_DIR / "is456_full_preprocessed.json"
    assert is456_file.exists(), "is456_full_preprocessed.json must exist"

    with open(is456_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("code") == "IS 456:2000"
    assert data.get("total_pages") == 114
    assert data.get("total_clauses_extracted") >= 350

    chunks = data.get("chunks", [])
    clause_numbers = [c["clause_number"] for c in chunks]

    # Verify structural sections are represented
    assert any("19" in num for num in clause_numbers)  # Loads & forces
    assert any("23" in num or "24" in num for num in clause_numbers)  # Beams / Slabs
    assert any("25" in num or "39" in num for num in clause_numbers)  # Columns
    assert any("34" in num for num in clause_numbers)  # Footings
    assert any("40" in num for num in clause_numbers)  # Shear
    assert any("Annex" in num for num in clause_numbers)  # Annexes


def test_is875_parts_preprocessed_integrity():
    """Step 3: Verifies IS 875 Part 1 (Dead loads) and Part 3 (Wind loads) are preprocessed."""
    p1_file = DATA_PROCESSED_DIR / "is875_part_1_preprocessed.json"
    p3_file = DATA_PROCESSED_DIR / "is875_part_3_preprocessed.json"

    assert p1_file.exists(), "is875_part_1_preprocessed.json must exist"
    assert p3_file.exists(), "is875_part_3_preprocessed.json must exist"

    with open(p1_file, "r", encoding="utf-8") as f:
        data1 = json.load(f)
    assert data1["total_pages"] == 43
    assert data1["total_clauses_extracted"] >= 15

    with open(p3_file, "r", encoding="utf-8") as f:
        data3 = json.load(f)
    assert data3["total_pages"] == 69
    assert data3["total_clauses_extracted"] >= 100

