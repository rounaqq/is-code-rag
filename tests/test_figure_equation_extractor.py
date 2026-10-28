"""
Unit tests for Step 3 (Document Preprocessing) - figure & equation extraction.

These tests build a small synthetic PDF with PyMuPDF so they are fully
deterministic and do not depend on the (git-ignored) IS code PDFs. They also
sanity-check the generated corpus index and any enriched preprocessed JSON.
"""

import json
from pathlib import Path

import pymupdf
import pytest

from src.ingestion import figure_equation_extractor as fee


DATA_PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"


def _make_synthetic_pdf(path: Path) -> None:
    """One page: a large raster image with a caption below it, plus formula lines."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)

    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 240, 180))
    pixmap.set_rect(pymupdf.IRect(0, 0, 240, 180), (180, 180, 180))
    page.insert_image(pymupdf.Rect(120, 120, 420, 320), pixmap=pixmap)

    page.insert_text((120, 345), "FIG. 1 SYNTHETIC TEST FIGURE")
    page.insert_text((120, 390), "Mu = 0.87 fy Ast d")
    page.insert_text((120, 410), "N/mm2")
    page.insert_text((120, 430), "(1)")
    page.insert_text((120, 450), "D = Overall depth of beam")
    doc.save(str(path))
    doc.close()


def test_code_slug_is_filesystem_safe():
    assert fee.code_slug("IS 456:2000") == "IS456-2000"
    assert fee.code_slug("IS 875 (Part 2):1987") == "IS875Part2-1987"


def test_is_equation_line_discriminates_formulas_from_noise():
    assert fee.is_equation_line("Mu = 0.87 fy Ast d")
    assert fee.is_equation_line("pt <= 4.0 percent")
    assert not fee.is_equation_line("N/mm2")
    assert not fee.is_equation_line("D = Overall depth of beam")  # bare notation, no digit
    assert not fee.is_equation_line("")
    assert not fee.is_equation_line("The beam shall be designed as a ductile member")


def test_extract_page_figures_renders_image_and_links_caption(tmp_path):
    pdf_path = tmp_path / "synthetic.pdf"
    _make_synthetic_pdf(pdf_path)

    doc = pymupdf.open(str(pdf_path))
    page = doc[0]
    figures = fee.extract_page_figures(
        page, "IS 456:2000", 1, tmp_path / "figures", text_blocks=page.get_text("blocks")
    )
    doc.close()

    assert len(figures) == 1
    figure = figures[0]
    assert figure["type"] == "figure"
    assert figure["label"] == "FIG. 1"
    assert figure["caption"].startswith("FIG. 1")
    assert figure["page_number"] == 1
    assert (tmp_path / "figures" / f"{figure['figure_id']}.png").exists()


def test_extract_page_equations_crops_formulas_only(tmp_path):
    pdf_path = tmp_path / "synthetic.pdf"
    _make_synthetic_pdf(pdf_path)

    doc = pymupdf.open(str(pdf_path))
    page = doc[0]
    equations = fee.extract_page_equations(
        page, "IS 456:2000", 1, tmp_path / "equations", text_dict=page.get_text("dict")
    )
    doc.close()

    texts = [e["text"] for e in equations]
    assert any("0.87" in t for t in texts), f"formula line missing: {texts}"
    assert any(e["label"] == "(1)" for e in equations), "numbered equation not captured"
    assert not any(t.strip() == "N/mm2" for t in texts), "unit string captured as an equation"
    assert not any(t.startswith("D = Overall") for t in texts), "notation captured as an equation"
    for equation in equations:
        assert (tmp_path / "equations" / f"{equation['equation_id']}.png").exists()


def test_extract_document_media(tmp_path, monkeypatch):
    pdf_path = tmp_path / "synthetic.pdf"
    _make_synthetic_pdf(pdf_path)

    monkeypatch.setattr(fee, "FIGURES_DIR", tmp_path / "figures")
    monkeypatch.setattr(fee, "EQUATIONS_DIR", tmp_path / "equations")
    monkeypatch.setattr(fee, "_needs_ocr", lambda page: False)

    media = fee.extract_document_media(pdf_path, "IS 456:2000")

    assert media["total_pages"] == 1
    assert media["figure_count"] == len(media["figures"]) == 1
    assert media["equation_count"] == len(media["equations"]) >= 1


def test_attach_media_to_document_adds_page_and_top_level_references():
    document = {"pages": [{"page_number": 1}, {"page_number": 2}]}
    media = {
        "figures": [{"figure_id": "F1", "page_number": 1}],
        "equations": [{"equation_id": "E1", "page_number": 2}],
        "figure_count": 1,
        "equation_count": 1,
    }

    fee.attach_media_to_document(document, media)

    assert document["pages"][0]["figure_ids"] == ["F1"]
    assert document["pages"][0]["equation_ids"] == []
    assert document["pages"][1]["equation_ids"] == ["E1"]
    assert document["figure_count"] == 1
    assert document["equation_count"] == 1


def test_generated_media_index_is_well_formed():
    """Sanity-check the real corpus index if the extractor has been run."""
    index_file = DATA_PROCESSED_DIR / "figures_equations.json"
    if not index_file.exists():
        pytest.skip("media index not generated yet")
    with open(index_file, "r", encoding="utf-8") as f:
        index = json.load(f)

    assert "documents" in index and "totals" in index
    for document in index["documents"]:
        assert document["figure_count"] == len(document["figures"])
        assert document["equation_count"] == len(document["equations"])
        for figure in document["figures"]:
            assert figure["figure_id"]
            assert figure["image_path"].endswith(".png")
            assert figure["code"] == document["code"]
        for equation in document["equations"]:
            assert equation["equation_id"]
            assert equation["image_path"].endswith(".png")


def test_preprocessed_documents_carry_media_metadata():
    """Any preprocessed JSON that has been enriched must be internally consistent."""
    for pre_path in DATA_PROCESSED_DIR.glob("*_preprocessed.json"):
        with open(pre_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "figures" not in data:
            continue
        assert data["figure_count"] == len(data["figures"])
        assert data["equation_count"] == len(data["equations"])
