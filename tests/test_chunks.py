"""
Unit tests for data/processed/chunks.jsonl.
Validates chunk count, uniqueness, verification status, clean text, Table 19 values,
and context paths across all 23 chunks.
"""

import json
from pathlib import Path

CHUNKS_FILE = Path("data/processed/chunks.jsonl")
TABLE_19_FILE = Path("data/processed/is456_table_19.json")


def load_chunks():
    assert CHUNKS_FILE.exists(), f"File not found: {CHUNKS_FILE}"
    chunks = []
    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                chunks.append(json.loads(line.strip()))
    return chunks


def test_chunks_count_and_uniqueness():
    """Checks that there are exactly 23 chunks and every chunk_id is unique."""
    chunks = load_chunks()
    assert len(chunks) == 23, f"Expected 23 chunks, got {len(chunks)}"

    chunk_ids = [c["chunk_id"] for c in chunks]
    unique_ids = set(chunk_ids)
    assert len(unique_ids) == 23, f"Duplicate chunk_id found: {chunk_ids}"


def test_every_chunk_verified():
    """Checks that every chunk has verified == True."""
    chunks = load_chunks()
    unverified = [c["chunk_id"] for c in chunks if not c.get("verified")]
    assert not unverified, f"Chunks not marked verified: {unverified}"


def test_no_unverified_or_ocr_in_text():
    """Checks that no chunk text contains 'UNVERIFIED' or 'OCR:'."""
    chunks = load_chunks()
    violations = {}
    for c in chunks:
        text = c.get("text", "")
        issues = []
        if "UNVERIFIED" in text:
            issues.append("Contains 'UNVERIFIED'")
        if "OCR:" in text:
            issues.append("Contains 'OCR:'")
        if issues:
            violations[c["chunk_id"]] = issues

    assert not violations, f"Found UNVERIFIED/OCR: in chunk text: {violations}"


def test_table_19_contains_all_78_values():
    """Checks that the Table 19 chunk text contains all 78 values from is456_table_19.json."""
    chunks = load_chunks()
    t19_chunk = next((c for c in chunks if c["chunk_id"] == "IS456-2000-TABLE-19"), None)
    assert t19_chunk is not None, "Table 19 chunk not found"

    with open(TABLE_19_FILE, "r", encoding="utf-8") as f:
        t19_data = json.load(f)

    missing = []
    for r in t19_data["rows"]:
        for grade, val in r["tau_c"].items():
            formatted = f"{val:.2f}"
            if formatted not in t19_chunk["text"] and str(val) not in t19_chunk["text"]:
                missing.append((r["pt_label"], grade, val))

    assert not missing, f"Missing {len(missing)} values from Table 19 chunk text: {missing}"


def test_clause_and_table_chunks_context_path():
    """Checks that chunks have accurate context_paths according to IS 456 hierarchy."""
    chunks = load_chunks()
    for c in chunks:
        cid = c["chunk_id"]
        cp = c.get("context_path")
        if "CL-26.5.1" in cid:
            assert cp is not None and "Beams" in cp, f"'Beams' not in context_path for {cid}"
        elif "ANNEX-G" in cid:
            assert cp == "IS 456 > Annex G Moments of resistance for rectangular and T-sections", f"Unexpected context_path for {cid}"
        elif "CL-40" in cid or cid == "IS456-2000-TABLE-20":
            assert cp == "IS 456 > 40 Limit state of collapse: shear", f"Unexpected context_path for {cid}"
        elif cid == "IS456-2000-TABLE-XU-MAX-38.1":
            assert cp == "IS 456 > 38 Limit state of collapse: flexure", f"Unexpected context_path for {cid}"
        elif cid in ("IS456-2000-TABLE-16", "IS456-2000-TABLE-19"):
            assert cp is None, f"Expected None context_path for {cid}, got {cp}"
