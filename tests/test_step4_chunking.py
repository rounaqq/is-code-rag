"""
Unit and integration tests for Step 4: Chunking & Metadata Enrichment.

Verifies:
- Clause-level granularity with dedicated chunk types ('clause', 'table', 'amendment', 'errata', 'example').
- Metadata enrichment schema enforcing: IS code number, year, amendment, section, clause number,
  title, applicability, keywords, dependencies.
- Unified enriched chunks dataset (data/processed/all_enriched_chunks.jsonl).
- PostgreSQL JSONB Document Store insertion and query operators.
"""

import json
from pathlib import Path
import pytest

from src.chunking.schema import ClauseChunk, EnrichedChunk
from src.storage.postgres_db import get_store

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
ENRICHED_CHUNKS_FILE = DATA_PROCESSED_DIR / "all_enriched_chunks.jsonl"


def test_clause_chunk_schema_supports_all_step4_metadata_fields():
    """Step 4: ClauseChunk Pydantic schema carries all required metadata fields."""
    sample = {
        "code_id": "IS 456:2000",
        "edition_year": 2000,
        "amendment": "Amendment No. 1",
        "section": "Section 3 General Design Considerations",
        "clause_number": "26.5.1.1(a)",
        "clause_title": "Minimum tension reinforcement",
        "applicability": "RC Beams",
        "keywords": ["IS 456", "tension steel", "minimum"],
        "dependencies": ["IS 456:2000", "IS 1786"],
        "chunk_type": "clause",
        "page_number": [59, 60],
        "raw_text": "As/(bd) >= 0.85/fy",
        "cleaned_text": "As/(bd) >= 0.85/fy",
        "cross_references": ["IS 1786"],
        "verified": True,
        "verified_text": "As/(bd) >= 0.85/fy",
    }
    chunk = ClauseChunk(**sample)
    assert chunk.code_id == "IS 456:2000"
    assert chunk.amendment == "Amendment No. 1"
    assert chunk.section == "Section 3 General Design Considerations"
    assert chunk.applicability == "RC Beams"
    assert "IS 1786" in chunk.dependencies
    assert chunk.chunk_type == "clause"
    assert chunk.embedding_text == "As/(bd) >= 0.85/fy"


def test_enriched_chunk_pydantic_validation():
    """Step 4: EnrichedChunk model validates complete metadata payload."""
    sample = {
        "chunk_id": "TEST-CHUNK-01",
        "code": "IS 13920:2016",
        "year": 2016,
        "amendment": "Amendment No. 1",
        "section": "Beams (Flexural Ductility)",
        "clause_number": "6.3.3",
        "title": "Beam Support Confinement Zone",
        "applicability": "Seismic Ductile Detailing",
        "keywords": ["IS 13920", "confinement", "stirrups"],
        "dependencies": ["IS 1893:2016"],
        "chunk_type": "clause",
        "text": "Over a length equal to 2d from the face of each support...",
        "cross_references": ["IS 1893"],
        "equations": ["s <= min(d/4, 8*db, 100 mm)"],
        "verified": True,
    }
    chunk = EnrichedChunk(**sample)
    assert chunk.chunk_id == "TEST-CHUNK-01"
    assert chunk.clause_number == "6.3.3"
    assert len(chunk.equations) == 1
    assert chunk.chunk_type == "clause"


def test_all_enriched_chunks_file_exists_and_parses():
    """Step 4: all_enriched_chunks.jsonl exists and contains over 1500 valid enriched chunks."""
    assert ENRICHED_CHUNKS_FILE.exists(), f"File missing at {ENRICHED_CHUNKS_FILE}"

    total_chunks = 0
    chunk_types = set()
    codes = set()

    with open(ENRICHED_CHUNKS_FILE, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            line_str = line.strip()
            if not line_str:
                continue
            data = json.loads(line_str)
            chunk = EnrichedChunk(**data)

            assert chunk.chunk_id, f"Missing chunk_id at line {idx}"
            assert chunk.code, f"Missing code at line {idx}"
            assert chunk.title, f"Missing title at line {idx}"
            assert chunk.applicability, f"Missing applicability at line {idx}"
            assert len(chunk.keywords) > 0, f"Empty keywords at line {idx}"
            assert len(chunk.dependencies) > 0, f"Empty dependencies at line {idx}"

            chunk_types.add(chunk.chunk_type)
            codes.add(chunk.code)
            total_chunks += 1

    assert total_chunks >= 1500, f"Expected >= 1500 chunks, found {total_chunks}"
    assert "clause" in chunk_types
    assert "table" in chunk_types
    assert "amendment" in chunk_types
    assert "errata" in chunk_types
    assert "example" in chunk_types

    # Ensure major standards are in the unified chunk compilation
    assert any("456" in c for c in codes)
    assert any("13920" in c for c in codes)
    assert any("1893" in c for c in codes)
    assert any("800" in c for c in codes)
    assert any("875" in c for c in codes)


def test_postgres_document_store_live_connection():
    """Step 4: PostgreSQL document store connection and query operations."""
    store = get_store()
    if not store.conn:
        pytest.skip("PostgreSQL service not connected; skipping live DB test.")

    total_in_db = store.count_chunks()
    assert total_in_db >= 1500, f"Expected >= 1500 chunks in DB, found {total_in_db}"

    # Query by code
    is456_chunks = store.query_by_code("IS 456:2000")
    assert len(is456_chunks) > 0

    # Query specific clause
    cl_chunk = store.get_chunk("IS456-2000-CL-26.5.1.1(a)")
    if not cl_chunk:
        cl_chunk = store.query_by_clause("IS 456:2000", "26.5.1.1(a)")
    assert cl_chunk is not None
    assert "26.5.1.1" in str(cl_chunk.get("clause_number", ""))

    # Query by metadata
    beams_by_applicability = store.query_by_metadata("applicability", "RC Beams (Flexure, Shear & Deflection)")
    assert len(beams_by_applicability) > 0
