"""
Step 3 (Document Preprocessing) - Figure & Equation Extraction.

Complements the OCR / text pipeline in ``ocr_preprocessor.py`` by pulling the
non-textual engineering content out of the official IS code PDFs:

* Raster figures - embedded and inline images are located on each page
  (full-page scan backgrounds and decorative glyphs are skipped) and rendered
  to PNG.
* Figure captions - "FIG. n", "Fig. n" and "Figure n" captions are detected and
  linked to the nearest figure region on the same page.
* Equations - numbered equation references (a standalone "(1)") and formula
  lines carrying an equals sign are cropped to PNG with their extracted text
  preserved, so the deterministic maths in this project never depends on an LLM
  re-typing a formula.

Pages whose native text layer is corrupt (BIS proprietary font encoding, e.g.
IS 13920 and IS 1893) are transparently re-read through the same Tesseract OCR
fallback used by ``ocr_preprocessor.py`` so captions and equations are legible.

Outputs
-------
data/processed/figures/<CODE>_p<page>_fig<n>.png
data/processed/equations/<CODE>_p<page>_eq<n>.png
data/processed/figures_equations.json   (unified index across the corpus)

The index can also be merged into the Step-4 preprocessed JSON files so that
every page record carries its ``figures`` / ``equations`` references.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pymupdf


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
TESSDATA_DIR = PROJECT_ROOT / "data" / "tessdata"
REGISTRY_FILE = DATA_RAW_DIR / "registry.json"
FIGURES_DIR = DATA_PROCESSED_DIR / "figures"
EQUATIONS_DIR = DATA_PROCESSED_DIR / "equations"
INDEX_FILE = DATA_PROCESSED_DIR / "figures_equations.json"

# Figure captions: "FIG. 2 ...", "Fig. 14.", "Figure 4"
FIGURE_CAPTION_RE = re.compile(
    r"^\s*(?:FIG(?:URE)?\.?)\s*\.?\s*(\d+[A-Za-z]?)\b[\s\.\:\-]*(.*)$",
    re.IGNORECASE,
)
# Standalone numbered equation reference, e.g. "(1)" or "(2a)"
EQUATION_NUMBER_RE = re.compile(r"^\s*\(\s*(\d+[a-z]?)\s*\)\s*$")
# Inequality operators that appear in codified design constraints (pt <= 4.0%)
INEQUALITY_CHARS = ("≤", "≥", "<", ">")

RENDER_DPI = 150
OCR_DPI = 200
CAPTION_SEARCH_GAP_PT = 45.0
MIN_FIGURE_WIDTH_PT = 60.0
MIN_FIGURE_HEIGHT_PT = 40.0
MIN_FIGURE_AREA_PT2 = 3000.0
FULL_PAGE_AREA_RATIO = 0.85


def code_slug(code_id: str) -> str:
    """Filesystem-safe short identifier for a standard, e.g. 'IS 456:2000' -> 'IS456-2000'."""
    return code_id.replace(" ", "").replace(":", "-").replace("(", "").replace(")", "")


def _rel(path: Path) -> str:
    """Project-relative POSIX path when possible, otherwise the absolute path."""
    try:
        return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def is_equation_line(text: str, min_len: int = 4, max_len: int = 110) -> bool:
    """
    Heuristic for a formula line:
    * carries an equals sign with operands on both sides and at least one digit
      (this rejects prose and bare notation like 'D = Overall depth of beam'), or
    * is a short digit-bearing inequality constraint (e.g. pt <= 4.0%).
    Plain unit strings such as 'N/mm2' are rejected.
    """
    stripped = text.strip()
    if not (min_len <= len(stripped) <= max_len):
        return False

    if "=" in stripped and any(ch.isdigit() for ch in stripped):
        left, _, right = stripped.partition("=")
        return bool(left.strip()) and bool(right.strip())

    if any(op in stripped for op in INEQUALITY_CHARS) and any(ch.isdigit() for ch in stripped):
        words = [w for w in stripped.split() if w.isalpha()]
        return len(words) <= 6

    return False


def _render_clip(page: pymupdf.Page, clip: pymupdf.Rect, out_path: Path, dpi: int = RENDER_DPI) -> None:
    """Render a page region to a PNG file."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pix = page.get_pixmap(clip=clip, dpi=dpi)
    pix.save(str(out_path))


def _needs_ocr(page: pymupdf.Page) -> bool:
    """True when the page's native text layer is empty or font-corrupted."""
    try:
        from src.ingestion.ocr_preprocessor import is_text_corrupt_or_empty

        return is_text_corrupt_or_empty(page.get_text())
    except Exception:
        # Conservative fallback if the preprocessor is unavailable.
        return len(page.get_text().strip()) < 50


def _page_text(
    page: pymupdf.Page, tessdata_path: Optional[Path] = None
) -> Tuple[List[Any], Dict[str, Any], str]:
    """
    Returns (blocks, text_dict, method) for a page, running Tesseract OCR when
    the native text layer is corrupt. ``method`` is 'direct' or 'ocr'.
    """
    if not _needs_ocr(page):
        return page.get_text("blocks"), page.get_text("dict"), "direct"

    if tessdata_path is None:
        tessdata_path = TESSDATA_DIR
    try:
        textpage = page.get_textpage_ocr(tessdata=str(tessdata_path), dpi=OCR_DPI, language="eng")
        blocks = page.get_text("blocks", textpage=textpage)
        text_dict = page.get_text("dict", textpage=textpage)
        if blocks:
            return blocks, text_dict, "ocr"
    except Exception as exc:  # pragma: no cover - depends on OCR availability
        print(f"    [WARN] OCR text extraction failed on page {page.number + 1}: {exc}")

    return page.get_text("blocks"), page.get_text("dict"), "direct_fallback"


def _find_caption_below(
    figure_bbox: pymupdf.Rect, text_blocks: List[Any]
) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (label, caption_text) for the figure caption closest below the
    figure region within ``CAPTION_SEARCH_GAP_PT``.
    """
    best: Optional[Tuple[float, str, str]] = None
    for block in text_blocks:
        x0, y0, x1, y1, text = block[0], block[1], block[2], block[3], block[4]
        if not isinstance(text, str) or not text.strip():
            continue
        gap = y0 - figure_bbox.y1
        if gap < -5 or gap > CAPTION_SEARCH_GAP_PT:
            continue
        if x1 < figure_bbox.x0 or x0 > figure_bbox.x1:
            continue
        match = FIGURE_CAPTION_RE.match(text.strip())
        if not match:
            continue
        label = f"FIG. {match.group(1)}"
        caption = " ".join(text.split())
        if best is None or gap < best[0]:
            best = (gap, label, caption)
    if best is None:
        return None, None
    return best[1], best[2]


def extract_page_figures(
    page: pymupdf.Page,
    code: str,
    page_no: int,
    figures_dir: Path,
    text_blocks: Optional[List[Any]] = None,
    min_width: float = MIN_FIGURE_WIDTH_PT,
    min_height: float = MIN_FIGURE_HEIGHT_PT,
    min_area: float = MIN_FIGURE_AREA_PT2,
) -> List[Dict[str, Any]]:
    """Locate and render the raster figures placed on a single page."""
    page_area = page.rect.width * page.rect.height
    figures: List[Dict[str, Any]] = []
    counter = 0

    for info in page.get_image_info(xrefs=True):
        bbox = pymupdf.Rect(info["bbox"])
        width, height = bbox.width, bbox.height
        area = width * height
        if area <= 0:
            continue
        # Skip the full-page scan background used by photographic PDFs.
        if area >= FULL_PAGE_AREA_RATIO * page_area:
            continue
        # Skip small decorative glyphs, logos and rule lines.
        if width < min_width or height < min_height or area < min_area:
            continue

        counter += 1
        figure_id = f"{code_slug(code)}-p{page_no}-fig{counter}"
        image_path = figures_dir / f"{figure_id}.png"
        _render_clip(page, bbox, image_path)
        label, caption = _find_caption_below(bbox, text_blocks or [])

        figures.append(
            {
                "figure_id": figure_id,
                "code": code,
                "page_number": page_no,
                "type": "figure",
                "label": label,
                "caption": caption,
                "bbox": [round(v, 1) for v in (bbox.x0, bbox.y0, bbox.x1, bbox.y1)],
                "width_pt": round(width, 1),
                "height_pt": round(height, 1),
                "image_path": _rel(image_path),
            }
        )
    return figures


def extract_page_equations(
    page: pymupdf.Page,
    code: str,
    page_no: int,
    equations_dir: Path,
    text_dict: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Detect formula lines / numbered equations on a page and crop them."""
    equations: List[Dict[str, Any]] = []
    counter = 0
    if text_dict is None:
        text_dict = page.get_text("dict")

    for block in text_dict.get("blocks", []):
        for line in block.get("lines", []):
            text = "".join(span["text"] for span in line.get("spans", [])).strip()
            if not text:
                continue
            number_match = EQUATION_NUMBER_RE.match(text)
            if number_match:
                label = f"({number_match.group(1)})"
            elif is_equation_line(text):
                label = None
            else:
                continue

            counter += 1
            equation_id = f"{code_slug(code)}-p{page_no}-eq{counter}"
            bbox = pymupdf.Rect(line["bbox"])
            # Pad the crop so the full formula (with superscripts) is captured.
            padded = pymupdf.Rect(bbox.x0 - 4, bbox.y0 - 3, bbox.x1 + 4, bbox.y1 + 3)
            image_path = equations_dir / f"{equation_id}.png"
            _render_clip(page, padded, image_path)

            equations.append(
                {
                    "equation_id": equation_id,
                    "code": code,
                    "page_number": page_no,
                    "type": "equation",
                    "label": label,
                    "text": " ".join(text.split()),
                    "bbox": [round(v, 1) for v in (bbox.x0, bbox.y0, bbox.x1, bbox.y1)],
                    "image_path": _rel(image_path),
                }
            )
    return equations


def extract_document_media(
    pdf_path: Path, code: str, tessdata_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Extract every figure and equation from one PDF and render the crops."""
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = pymupdf.open(str(pdf_path))
    figures: List[Dict[str, Any]] = []
    equations: List[Dict[str, Any]] = []
    ocr_pages = 0

    print(f"\n[MEDIA EXTRACTION] {code} ({pdf_path.name}) - {len(doc)} pages")
    for page_index in range(len(doc)):
        page = doc[page_index]
        page_no = page_index + 1
        blocks, text_dict, method = _page_text(page, tessdata_path=tessdata_path)
        if method == "ocr":
            ocr_pages += 1
        figures.extend(extract_page_figures(page, code, page_no, FIGURES_DIR, text_blocks=blocks))
        equations.extend(extract_page_equations(page, code, page_no, EQUATIONS_DIR, text_dict=text_dict))
        if page_no % 10 == 0 or page_no == len(doc):
            sys.stdout.write(
                f"\r  Scanned page {page_no}/{len(doc)} (OCR pages: {ocr_pages}, figures: {len(figures)}, equations: {len(equations)})"
            )
            sys.stdout.flush()
    print()

    return {
        "code": code,
        "source_pdf": pdf_path.name,
        "total_pages": len(doc),
        "ocr_pages": ocr_pages,
        "figure_count": len(figures),
        "equation_count": len(equations),
        "figures": figures,
        "equations": equations,
    }


def _registry_documents() -> List[Dict[str, str]]:
    """All acquired documents from the Step-2 registry, in registry order."""
    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        registry = json.load(f)
    docs = []
    for entry in registry.get("standards", []) + registry.get("handbooks", []):
        if entry.get("status") != "acquired":
            continue
        docs.append({"code": entry["code"], "filename": entry["filename"]})
    return docs


def _clean_generated_media() -> None:
    """Remove previously generated media crops so a full re-run leaves no orphans."""
    for directory in (FIGURES_DIR, EQUATIONS_DIR):
        if directory.exists():
            for png in directory.glob("*.png"):
                png.unlink()


def _load_existing_index() -> Dict[str, Any]:
    """Load the current media index, or an empty skeleton if none exists yet."""
    if INDEX_FILE.exists():
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"generated_by": "src/ingestion/figure_equation_extractor.py", "documents": [], "totals": {}}


def run_extraction(code_filter: Optional[str] = None, merge_preprocessed: bool = True) -> Dict[str, Any]:
    """
    Extract media from every acquired PDF and write the unified index.

    A full run (``code_filter=None``) clears and rebuilds all media. A filtered
    run updates just the requested document in the existing index.
    """
    order = [entry["code"] for entry in _registry_documents()]

    if code_filter is None:
        _clean_generated_media()
        existing: List[Dict[str, Any]] = []
    else:
        existing = [d for d in _load_existing_index().get("documents", []) if d["code"] != code_filter]

    documents: List[Dict[str, Any]] = existing
    for entry in _registry_documents():
        if code_filter and entry["code"] != code_filter:
            continue
        pdf_path = DATA_RAW_DIR / entry["filename"]
        if not pdf_path.exists():
            print(f"[SKIP] {entry['code']}: {entry['filename']} not found in {DATA_RAW_DIR}")
            continue
        documents.append(extract_document_media(pdf_path, entry["code"]))

    documents.sort(key=lambda d: order.index(d["code"]) if d["code"] in order else len(order))

    index = {
        "generated_by": "src/ingestion/figure_equation_extractor.py",
        "documents": documents,
        "totals": {
            "figures": sum(d["figure_count"] for d in documents),
            "equations": sum(d["equation_count"] for d in documents),
            "documents": len(documents),
        },
    }

    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    print(
        f"\n[SAVED] Media index -> {INDEX_FILE.name} "
        f"({index['totals']['figures']} figures, {index['totals']['equations']} equations)"
    )

    if merge_preprocessed:
        merge_index_into_preprocessed(index)

    return index


def attach_media_to_document(document: Dict[str, Any], media: Dict[str, Any]) -> None:
    """Attach figure/equation references from ``media`` onto a preprocessed document dict."""
    figures_by_page: Dict[int, List[str]] = {}
    for fig in media["figures"]:
        figures_by_page.setdefault(fig["page_number"], []).append(fig["figure_id"])
    equations_by_page: Dict[int, List[str]] = {}
    for eq in media["equations"]:
        equations_by_page.setdefault(eq["page_number"], []).append(eq["equation_id"])

    for page in document.get("pages", []):
        page_no = page.get("page_number")
        page["figure_ids"] = figures_by_page.get(page_no, [])
        page["equation_ids"] = equations_by_page.get(page_no, [])

    document["figures"] = media["figures"]
    document["equations"] = media["equations"]
    document["figure_count"] = media["figure_count"]
    document["equation_count"] = media["equation_count"]


def merge_index_into_preprocessed(index: Dict[str, Any]) -> int:
    """
    Attach figure/equation references to the matching Step-4 preprocessed JSON
    files (matched on the document ``code``). Returns the number of files updated.
    """
    by_code = {doc["code"]: doc for doc in index.get("documents", [])}
    updated = 0

    for pre_path in sorted(DATA_PROCESSED_DIR.glob("*_preprocessed.json")):
        with open(pre_path, "r", encoding="utf-8") as f:
            pre = json.load(f)
        media = by_code.get(pre.get("code"))
        if not media:
            continue

        attach_media_to_document(pre, media)

        with open(pre_path, "w", encoding="utf-8") as f:
            json.dump(pre, f, indent=2, ensure_ascii=False)
        updated += 1
        print(
            f"  [MERGED] {len(media['figures'])} figures / {len(media['equations'])} equations -> {pre_path.name}"
        )

    return updated


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Figure & Equation Extractor for IS Code PDFs")
    parser.add_argument("--code", type=str, default=None, help="Limit to one registry code, e.g. 'IS 456:2000'")
    parser.add_argument("--no-merge", action="store_true", help="Do not merge results into preprocessed JSON")
    args = parser.parse_args()

    run_extraction(code_filter=args.code, merge_preprocessed=not args.no_merge)
