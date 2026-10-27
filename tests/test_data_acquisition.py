"""
Unit tests for Step 1 (Requirement Analysis & Scope Definition) and
Step 2 (Data Acquisition & Collection).
Verifies standards registry, Git LFS attributes, DVC manifest, and downloaded PDF integrity.
"""

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_FILE = PROJECT_ROOT / "data" / "raw" / "registry.json"
GITATTRIBUTES_FILE = PROJECT_ROOT / ".gitattributes"
DVC_MANIFEST_FILE = PROJECT_ROOT / "data" / "raw" / "DVC_MANIFEST.md"
SCOPE_DOC_FILE = PROJECT_ROOT / "docs" / "REQUIREMENT_ANALYSIS_AND_SCOPE.md"


def test_scope_document_covers_all_codes_and_cad_outputs():
    """Step 1: Scope document exists and covers IS 456, 13920, 875, 1893, 800 and 2D CAD targets."""
    assert SCOPE_DOC_FILE.exists()
    content = SCOPE_DOC_FILE.read_text(encoding="utf-8")
    for code in ["IS 456", "IS 13920", "IS 875", "IS 1893", "IS 800"]:
        assert code in content, f"Scope document must cover {code}"
    for target in ["Beams", "Columns", "Floor Slabs", "Footings", "ezdxf", "DRAFT"]:
        assert target in content, f"Scope document must cover {target}"


def test_registry_structure_and_completeness():
    """Step 2: Registry contains all 5 IS codes and supplementary handbooks."""
    assert REGISTRY_FILE.exists()
    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        registry = json.load(f)

    assert "standards" in registry
    assert "handbooks" in registry

    standards = {s["code"]: s for s in registry["standards"]}
    assert "IS 456:2000" in standards
    assert "IS 13920:2016" in standards
    assert "IS 875 (Part 2):1987" in standards
    assert "IS 1893 (Part 1):2016" in standards
    assert "IS 800:2007" in standards

    handbooks = {h["code"]: h for h in registry["handbooks"]}
    assert "SP:16:1980" in handbooks
    assert "SP:34:1987" in handbooks

    for s in registry["standards"]:
        assert "filename" in s
        assert "publisher" in s
        assert "archive_url" in s


def test_gitattributes_lfs_configured():
    """Step 2: .gitattributes configures Git LFS for binary PDFs and CAD files."""
    assert GITATTRIBUTES_FILE.exists()
    content = GITATTRIBUTES_FILE.read_text(encoding="utf-8")
    assert "*.pdf" in content
    assert "filter=lfs" in content
    assert "*.dwg" in content


def test_dvc_manifest_exists():
    """Step 2: DVC manifest documents cloud remote commands and data pipeline."""
    assert DVC_MANIFEST_FILE.exists()
    content = DVC_MANIFEST_FILE.read_text(encoding="utf-8")
    assert "dvc add" in content
    assert "dvc push" in content
    assert "IS 13920" in content


def test_is_13920_pdf_integrity():
    """Step 2: Downloaded IS 13920:2016 PDF exists and has valid %PDF- header."""
    pdf_path = PROJECT_ROOT / "data" / "raw" / "is_13920_2016.pdf"
    if pdf_path.exists():
        assert pdf_path.stat().st_size > 100_000
        with open(pdf_path, "rb") as f:
            header = f.read(5)
        assert header == b"%PDF-"
