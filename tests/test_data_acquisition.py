"""
Unit tests for Step 1 (Requirement Analysis & Scope Definition) and
Step 2 (Data Acquisition & Collection).
Verifies standards registry, amendments, errata, supplementary design examples,
Git LFS attributes, DVC manifest, and downloaded PDF integrity across all 28 corpus documents.

Corpus checks require the DVC-tracked PDFs to be present. When the raw corpus has not
been restored (for example on a CI runner with no shared DVC remote), those checks are
reported as SKIPPED with a reason - never as passed.
"""

import hashlib
import json
from pathlib import Path
import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_FILE = PROJECT_ROOT / "data" / "raw" / "registry.json"
GITATTRIBUTES_FILE = PROJECT_ROOT / ".gitattributes"
DVC_MANIFEST_FILE = PROJECT_ROOT / "data" / "raw" / "DVC_MANIFEST.md"
DVC_CONFIG_FILE = PROJECT_ROOT / ".dvc" / "config"
SCOPE_DOC_FILE = PROJECT_ROOT / "docs" / "REQUIREMENT_ANALYSIS_AND_SCOPE.md"

CORPUS_MISSING_REASON = (
    "raw corpus not present in this checkout; restore it with 'dvc pull' "
    "(a shared DVC remote must be configured - see docs/DEPLOYMENT.md section 3)"
)


def _all_registry_entries():
    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        registry = json.load(f)
    return (
        registry.get("standards", [])
        + registry.get("handbooks", [])
        + registry.get("amendments", [])
        + registry.get("errata", [])
        + registry.get("design_examples", [])
    )


def test_scope_document_covers_all_codes_and_cad_outputs():
    """Step 1: Scope document exists and covers IS 456, 13920, 875, 1893, 800 and 2D CAD targets."""
    assert SCOPE_DOC_FILE.exists()
    content = SCOPE_DOC_FILE.read_text(encoding="utf-8")
    for code in ["IS 456", "IS 13920", "IS 875", "IS 1893", "IS 800"]:
        assert code in content, f"Scope document must cover {code}"
    for target in ["Beams", "Columns", "Floor Slabs", "Footings", "ezdxf", "DRAFT"]:
        assert target in content, f"Scope document must cover {target}"


def test_registry_structure_and_completeness():
    """Step 2: Registry contains standards, handbooks, amendments, errata, and design examples."""
    assert REGISTRY_FILE.exists()
    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        registry = json.load(f)

    assert "standards" in registry
    assert "handbooks" in registry
    assert "amendments" in registry
    assert "errata" in registry
    assert "design_examples" in registry

    standards = {s["code"]: s for s in registry["standards"]}
    assert "IS 456:2000" in standards
    assert "IS 13920:2016" in standards
    assert "IS 875 (Part 1):1987" in standards
    assert "IS 875 (Part 2):1987" in standards
    assert "IS 875 (Part 3):2015" in standards
    assert "IS 1893 (Part 1):2016" in standards
    assert "IS 800:2007" in standards

    handbooks = {h["code"]: h for h in registry["handbooks"]}
    assert "SP:16:1980" in handbooks
    assert "SP:34:1987" in handbooks
    assert "SP:24:1983" in handbooks

    # Amendments checking
    amendments = {a["code"]: a for a in registry["amendments"]}
    assert len(amendments) >= 13
    assert "IS 456:2000 / AMD 1" in amendments
    assert "IS 456:2000 / AMD 5" in amendments
    assert "IS 13920:2016 / AMD 1" in amendments
    assert "IS 13920:2016 / AMD 2" in amendments
    assert "IS 1893 (Part 1):2016 / AMD 1" in amendments
    assert "IS 800:2007 / AMD 1" in amendments

    # Errata checking
    errata = {e["code"]: e for e in registry["errata"]}
    assert len(errata) >= 2
    assert "IS 456:2000 / ERR 1" in errata
    assert "IS 800:2007 / ERR 1" in errata

    # Design examples checking
    examples = {d["code"]: d for d in registry["design_examples"]}
    assert "IITK-GSDMA EQ26" in examples
    assert "IITK-GSDMA EQ06" in examples
    assert "SP:16 Worked Examples" in examples


def test_registry_entries_are_acquired_and_integrity_tagged():
    """Step 2: Every single registry entry (28 documents) is acquired with URL, byte size, and SHA-256."""
    entries = _all_registry_entries()
    assert len(entries) == 28, f"Expected 28 corpus documents, found {len(entries)}"

    for entry in entries:
        code = entry["code"]
        assert entry["status"] == "acquired", f"{code} should be acquired"
        assert entry["archive_url"].startswith("http"), f"{code} needs a real archive_url"
        assert entry["file_size_bytes"] > 1000, f"{code} needs a plausible byte size (>1000 bytes)"
        sha256 = entry["sha256"]
        assert len(sha256) == 64, f"{code} must store a 64-char SHA-256 digest"
        int(sha256, 16)  # must be valid hex


def test_amendments_and_errata_metadata_integrity():
    """Step 2: Amendments and errata carry affected clauses, standard code, and issue dates."""
    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        registry = json.load(f)

    for amd in registry["amendments"]:
        assert "standard_code" in amd
        assert "amendment_number" in amd
        assert "issue_date" in amd
        assert "affected_clauses" in amd
        assert len(amd["affected_clauses"]) > 0

    for err in registry["errata"]:
        assert "standard_code" in err
        assert "errata_number" in err
        assert "affected_clauses" in err
        assert len(err["affected_clauses"]) > 0


def test_gitattributes_lfs_configured():
    """Step 2: .gitattributes configures Git LFS for binary PDFs and CAD files."""
    assert GITATTRIBUTES_FILE.exists()
    content = GITATTRIBUTES_FILE.read_text(encoding="utf-8")
    assert "*.pdf" in content
    assert "filter=lfs" in content
    assert "*.dwg" in content


def test_dvc_manifest_exists():
    """Step 2: DVC manifest documents cloud remote commands, amendments, and supplementary corpus."""
    assert DVC_MANIFEST_FILE.exists()
    content = DVC_MANIFEST_FILE.read_text(encoding="utf-8")
    assert "dvc add" in content
    assert "dvc push" in content
    assert "IS 13920" in content
    assert "amendments" in content.lower()
    assert "errata" in content.lower()
    assert "design example" in content.lower()


def test_dvc_repository_initialized_with_remote():
    """Step 2: DVC is truly initialized with a configured default remote."""
    assert DVC_CONFIG_FILE.exists(), ".dvc/config must exist (dvc init was run)"
    content = DVC_CONFIG_FILE.read_text(encoding="utf-8")
    assert "[core]" in content
    assert "remote" in content
    assert 'remote "' in content  # a named remote block is configured


def test_dvc_pointer_files_track_every_pdf():
    """Step 2: Each of the 28 acquired PDFs has a committed .dvc pointer file."""
    entries = _all_registry_entries()
    pointers = list(PROJECT_ROOT.glob("data/raw/**/*.pdf.dvc"))
    assert len(pointers) == len(entries), f"expected {len(entries)} .dvc pointers, found {len(pointers)}"

    for entry in entries:
        pointer = PROJECT_ROOT / "data" / "raw" / f"{entry['filename']}.dvc"
        assert pointer.exists(), f"missing DVC pointer for {entry['code']} at {pointer}"
        pointer_text = pointer.read_text(encoding="utf-8")
        assert "outs:" in pointer_text
        assert f"size: {entry['file_size_bytes']}" in pointer_text


def test_all_restored_pdfs_have_valid_pdf_headers():
    """Step 2: Every restored PDF exists and begins with %PDF- header."""
    entries = _all_registry_entries()
    for entry in entries:
        pdf_path = PROJECT_ROOT / "data" / "raw" / entry["filename"]
        if not pdf_path.exists():
            pytest.skip(CORPUS_MISSING_REASON)
        with open(pdf_path, "rb") as f:
            header = f.read(5)
        assert header == b"%PDF-", f"{entry['filename']} is not a valid PDF"


def test_restored_pdfs_match_registry_sha256():
    """Step 2: Every single restored PDF hashes to the exact SHA-256 recorded in registry.json."""
    entries = _all_registry_entries()
    restored = []
    for entry in entries:
        pdf_path = PROJECT_ROOT / "data" / "raw" / entry["filename"]
        if pdf_path.exists():
            restored.append((entry, pdf_path))

    if not restored:
        pytest.skip(CORPUS_MISSING_REASON)

    for entry, pdf_path in restored:
        digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        assert digest == entry["sha256"], (
            f"{entry['code']} ({entry['filename']}) does not match the SHA-256 in registry.json"
        )

    assert len(restored) == len(entries), (
        f"only {len(restored)}/{len(entries)} of the corpus is restored; run 'dvc pull' to fetch remaining PDFs"
    )


def test_download_codes_verification_routine():
    """Step 2: src.ingestion.download_codes.verify_all_corpus_files passes 100%."""
    from src.ingestion.download_codes import verify_all_corpus_files
    results = verify_all_corpus_files()
    assert results["total"] == 28
    assert results["valid"] == 28
    assert results["corrupt"] == 0
    assert results["missing"] == 0
