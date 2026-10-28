"""
Unit tests for Step 1 (Requirement Analysis & Scope Definition) and
Step 2 (Data Acquisition & Collection).
Verifies standards registry, Git LFS attributes, DVC manifest, and downloaded PDF integrity.

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
DVC_POINTER_GLOB = "data/raw/*.pdf.dvc"
SCOPE_DOC_FILE = PROJECT_ROOT / "docs" / "REQUIREMENT_ANALYSIS_AND_SCOPE.md"

CORPUS_MISSING_REASON = (
    "raw corpus not present in this checkout; restore it with 'dvc pull' "
    "(a shared DVC remote must be configured - see docs/DEPLOYMENT.md section 3)"
)


def _registry_entries():
    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        registry = json.load(f)
    return registry["standards"] + registry["handbooks"]


def test_scope_document_covers_all_codes_and_cad_outputs():
    """Step 1: Scope document exists and covers IS 456, 13920, 875, 1893, 800 and 2D CAD targets."""
    assert SCOPE_DOC_FILE.exists()
    content = SCOPE_DOC_FILE.read_text(encoding="utf-8")
    for code in ["IS 456", "IS 13920", "IS 875", "IS 1893", "IS 800"]:
        assert code in content, f"Scope document must cover {code}"
    for target in ["Beams", "Columns", "Floor Slabs", "Footings", "ezdxf", "DRAFT"]:
        assert target in content, f"Scope document must cover {target}"


def test_registry_structure_and_completeness():
    """Step 2: Registry contains all 7 IS standards and 3 supplementary handbooks."""
    assert REGISTRY_FILE.exists()
    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        registry = json.load(f)

    assert "standards" in registry
    assert "handbooks" in registry

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

    for s in registry["standards"]:
        assert "filename" in s
        assert "publisher" in s
        assert "archive_url" in s


def test_registry_entries_are_acquired_and_integrity_tagged():
    """Step 2: Every registry entry is acquired with a real URL, byte size, and SHA-256."""
    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        registry = json.load(f)

    entries = registry["standards"] + registry["handbooks"]
    assert len(entries) == 10

    for entry in entries:
        code = entry["code"]
        assert entry["status"] == "acquired", f"{code} should be acquired"
        assert entry["archive_url"].startswith("http"), f"{code} needs a real archive_url"
        assert entry["file_size_bytes"] > 1000, f"{code} needs a plausible byte size"
        sha256 = entry["sha256"]
        assert len(sha256) == 64, f"{code} must store a 64-char SHA-256 digest"
        int(sha256, 16)  # must be valid hex


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


def test_dvc_repository_initialized_with_remote():
    """Step 2: DVC is truly initialized with a configured default remote."""
    assert DVC_CONFIG_FILE.exists(), ".dvc/config must exist (dvc init was run)"
    content = DVC_CONFIG_FILE.read_text(encoding="utf-8")
    assert "[core]" in content
    assert "remote" in content
    assert 'remote "' in content  # a named remote block is configured


def test_dvc_pointer_files_track_every_pdf():
    """Step 2: Each acquired PDF has a committed .dvc pointer file."""
    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        registry = json.load(f)

    entries = registry["standards"] + registry["handbooks"]
    pointers = {p.name for p in PROJECT_ROOT.glob(DVC_POINTER_GLOB)}
    assert len(pointers) == len(entries), f"expected {len(entries)} .dvc pointers, found {len(pointers)}"

    for entry in entries:
        pointer = PROJECT_ROOT / "data" / "raw" / f"{entry['filename']}.dvc"
        assert pointer.exists(), f"missing DVC pointer for {entry['code']}"
        pointer_text = pointer.read_text(encoding="utf-8")
        assert "outs:" in pointer_text
        assert f"path: {entry['filename']}" in pointer_text
        assert f"size: {entry['file_size_bytes']}" in pointer_text


def test_is_13920_pdf_integrity():
    """Step 2: IS 13920:2016 PDF exists and has valid %PDF- header."""
    pdf_path = PROJECT_ROOT / "data" / "raw" / "is_13920_2016.pdf"
    if not pdf_path.exists():
        pytest.skip(CORPUS_MISSING_REASON)
    assert pdf_path.stat().st_size > 100_000
    with open(pdf_path, "rb") as f:
        header = f.read(5)
    assert header == b"%PDF-"


def test_restored_pdfs_match_registry_sha256():
    """
    Step 2: every restored PDF hashes to the SHA-256 recorded in the registry.

    This is the gate that gives the CI 'dvc pull' step meaning: whatever the runner
    restores must be byte-identical to the acquired, integrity-tagged corpus.
    """
    restored = []
    for entry in _registry_entries():
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

    assert len(restored) == len(_registry_entries()), (
        "only part of the corpus is restored; run 'dvc pull' to fetch the remaining PDFs"
    )
