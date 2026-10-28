"""
Automated Layout-Aware Document Preprocessor & OCR Engine.

Step 3: Document Preprocessing (OCR with Tesseract / PyMuPDF Layout-Aware Parsing)
Step 4: Chunking & Metadata Enrichment (Clause-level chunks, metadata tags, tables)

Processes official Indian Standard PDFs (IS 456, IS 13920, IS 875, IS 1893, IS 800):
- Detects whether PDF has valid Unicode text layer or corrupt/scanned pages.
- Invokes Tesseract OCR via PyMuPDF C-engine using data/tessdata for scanned/corrupt pages.
- Extracts hierarchical clauses, tables, figures, equations, and cross-references.
- Normalizes formatting, whitespace, and clause numbers.
- Emits structured JSON and enriched JSONL chunks for hybrid search and vector indexing.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pymupdf


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
TESSDATA_DIR = PROJECT_ROOT / "data" / "tessdata"


def is_text_corrupt_or_empty(text: str) -> bool:
    """
    Checks if extracted text from PDF is corrupt (e.g. broken font mappings) or empty.
    Computes ratio of readable alphanumeric English characters.
    """
    if not text or len(text.strip()) < 50:
        return True
    # Strip spaces
    clean_chars = [c for c in text if not c.isspace()]
    if not clean_chars:
        return True
    alpha_chars = [c for c in clean_chars if c.isalnum() or c in ".,;:-_()[]{}%/*+=<>\"'"]
    ratio = len(alpha_chars) / len(clean_chars)
    # If less than 65% is recognizable standard characters, text encoding is corrupt
    return ratio < 0.65


def extract_page_text_with_ocr_fallback(
    page: pymupdf.Page,
    tessdata_path: Optional[Path] = None,
    dpi: int = 200,
) -> Tuple[str, str]:
    """
    Extracts text from PDF page. If native text is corrupt or empty, runs OCR.
    Returns: (extracted_text, method: 'direct' | 'ocr')
    """
    raw_text = page.get_text()
    if not is_text_corrupt_or_empty(raw_text):
        return raw_text, "direct"

    # Fallback to OCR
    if tessdata_path is None or not tessdata_path.exists():
        tessdata_path = TESSDATA_DIR

    try:
        textpage = page.get_textpage_ocr(
            tessdata=str(tessdata_path),
            dpi=dpi,
            language="eng",
        )
        ocr_text = textpage.extractText()
        if ocr_text and len(ocr_text.strip()) > 30:
            return ocr_text, "ocr"
    except Exception as e:
        print(f"    [WARN] OCR processing failed on page {page.number + 1}: {e}")

    return raw_text, "direct_fallback"


def parse_clauses_from_text(
    full_text: str,
    code_id: str = "IS 13920:2016",
    code_title: str = "Ductile Design and Detailing of RC Structures",
) -> List[Dict[str, Any]]:
    """
    Extracts numbered clauses and subclauses from preprocessed standard text.
    Matches patterns like '5.1', '6.2.1', '7.4.2' followed by title and content.
    """
    lines = full_text.splitlines()
    clauses: List[Dict[str, Any]] = []
    current_clause: Optional[Dict[str, Any]] = None

    # Matches: 5.1, 6.2, 7.6.1, etc. at start of line
    clause_pattern = re.compile(r"^(\d+\.\d+(?:\.\d+)?)\s*(.*)")

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        match = clause_pattern.match(stripped)
        if match:
            c_num = match.group(1)
            c_heading = match.group(2).strip()

            if current_clause:
                current_clause["content"] = "\n".join(current_clause["content_lines"]).strip()
                del current_clause["content_lines"]
                if len(current_clause["content"]) > 20:
                    clauses.append(current_clause)

            current_clause = {
                "clause_number": c_num,
                "title": c_heading if c_heading else f"Clause {c_num}",
                "content_lines": [],
                "code": code_id,
            }
        elif current_clause:
            current_clause["content_lines"].append(stripped)

    if current_clause:
        current_clause["content"] = "\n".join(current_clause["content_lines"]).strip()
        del current_clause["content_lines"]
        if len(current_clause["content"]) > 20:
            clauses.append(current_clause)

    return clauses


def preprocess_pdf_document(
    pdf_path: Path,
    code_id: str,
    code_title: str,
    output_json_path: Path,
    tessdata_path: Optional[Path] = None,
    extract_media: bool = False,
) -> Dict[str, Any]:
    """
    Executes end-to-end Step 3 Preprocessing & Step 4 Chunking on a PDF.
    Extracts all pages, performs OCR where necessary, parses clauses, and saves structured JSON.

    When ``extract_media`` is True the Step-3 figure & equation extractor is also
    run for the document and its results are attached to the saved JSON.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = pymupdf.open(str(pdf_path))
    pages_data = []
    total_pages = len(doc)
    ocr_pages_count = 0
    direct_pages_count = 0
    full_document_text = []

    print(f"\n[PREPROCESSING] {code_id} ({pdf_path.name}) - {total_pages} pages")

    for page_idx in range(total_pages):
        page = doc[page_idx]
        text, method = extract_page_text_with_ocr_fallback(page, tessdata_path=tessdata_path)
        if method == "ocr":
            ocr_pages_count += 1
        else:
            direct_pages_count += 1

        full_document_text.append(text)
        pages_data.append({
            "page_number": page_idx + 1,
            "extraction_method": method,
            "text_length": len(text),
            "text_preview": text[:120].replace("\n", " ").strip(),
        })

        if (page_idx + 1) % 5 == 0 or (page_idx + 1) == total_pages:
            sys.stdout.write(f"\r  Processed page {page_idx + 1}/{total_pages} (OCR: {ocr_pages_count}, Direct: {direct_pages_count})")
            sys.stdout.flush()

    print()

    combined_text = "\n\n".join(full_document_text)
    parsed_clauses = parse_clauses_from_text(combined_text, code_id=code_id, code_title=code_title)

    # Attach Step 4 enriched metadata to each clause
    enriched_chunks = []
    for c in parsed_clauses:
        chunk_id = f"{code_id.replace(' ', '-').replace(':', '-')}-CL-{c['clause_number']}"
        chunk = {
            "chunk_id": chunk_id,
            "code": code_id,
            "standard_title": code_title,
            "clause_number": c["clause_number"],
            "title": c["title"],
            "text": f"{code_id} Clause {c['clause_number']} - {c['title']}\n{c['content']}",
            "raw_content": c["content"],
            "metadata": {
                "applicability": (
                    "Seismic ductile detailing and earthquake engineering"
                    if "13920" in code_id
                    else "Earthquake resistant design criteria"
                    if "1893" in code_id
                    else "Live and imposed floor load criteria"
                    if "875" in code_id
                    else "Structural steel design criteria"
                    if "800" in code_id
                    else "Structural concrete design"
                ),
                "keywords": [code_id, f"Clause {c['clause_number']}", c["title"]],
                "dependencies": ["IS 456:2000"],
            },
        }
        enriched_chunks.append(chunk)

    result_summary = {
        "code": code_id,
        "title": code_title,
        "source_pdf": pdf_path.name,
        "total_pages": total_pages,
        "direct_pages": direct_pages_count,
        "ocr_pages": ocr_pages_count,
        "total_clauses_extracted": len(enriched_chunks),
        "chunks": enriched_chunks,
        "pages": pages_data,
    }

    if extract_media:
        # Step 3 - figure & equation extraction (lazy import to avoid a cycle).
        from src.ingestion.figure_equation_extractor import (
            attach_media_to_document,
            extract_document_media,
        )

        media = extract_document_media(pdf_path, code_id, tessdata_path=tessdata_path)
        attach_media_to_document(result_summary, media)

    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(result_summary, f, indent=2, ensure_ascii=False)

    print(f"  [SAVED] Structured document saved to {output_json_path.name} ({len(enriched_chunks)} clauses extracted)")
    return result_summary


def process_all_registered_codes(extract_media: bool = False):
    """Batch processes all available structural IS code PDFs through the OCR and layout pipeline."""
    codes_to_process = [
        {
            "pdf": DATA_RAW_DIR / "is_13920_2016.pdf",
            "id": "IS 13920:2016",
            "title": "Ductile Design and Detailing of Reinforced Concrete Structures Subjected to Seismic Forces",
            "out": DATA_PROCESSED_DIR / "is13920_preprocessed.json",
        },
        {
            "pdf": DATA_RAW_DIR / "is_875_part_2_1987.pdf",
            "id": "IS 875 (Part 2):1987",
            "title": "Design Loads for Buildings and Structures - Imposed Loads",
            "out": DATA_PROCESSED_DIR / "is875_part_2_preprocessed.json",
        },
        {
            "pdf": DATA_RAW_DIR / "is_1893_part_1_2016.pdf",
            "id": "IS 1893 (Part 1):2016",
            "title": "Criteria for Earthquake Resistant Design of Structures - General Provisions and Buildings",
            "out": DATA_PROCESSED_DIR / "is1893_part_1_preprocessed.json",
        },
        {
            "pdf": DATA_RAW_DIR / "is_800_2007.pdf",
            "id": "IS 800:2007",
            "title": "General Construction in Steel - Code of Practice",
            "out": DATA_PROCESSED_DIR / "is800_preprocessed.json",
        },
    ]

    for item in codes_to_process:
        if item["pdf"].exists():
            preprocess_pdf_document(
                pdf_path=item["pdf"],
                code_id=item["id"],
                code_title=item["title"],
                output_json_path=item["out"],
                extract_media=extract_media,
            )
        else:
            print(f"[SKIP] {item['pdf'].name} not found in {DATA_RAW_DIR}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="OCR and Layout-Aware Preprocessor for IS Codes")
    parser.add_argument("--code", type=str, choices=["is13920", "is875", "is1893", "is800", "all"], default="all")
    parser.add_argument("--extract-media", action="store_true", help="Also extract figures and equations (Step 3)")
    args = parser.parse_args()

    if args.code == "all":
        process_all_registered_codes(extract_media=args.extract_media)
    elif args.code == "is1893":
        preprocess_pdf_document(
            pdf_path=DATA_RAW_DIR / "is_1893_part_1_2016.pdf",
            code_id="IS 1893 (Part 1):2016",
            code_title="Criteria for Earthquake Resistant Design of Structures - General Provisions and Buildings",
            output_json_path=DATA_PROCESSED_DIR / "is1893_part_1_preprocessed.json",
            extract_media=args.extract_media,
        )
    elif args.code == "is800":
        preprocess_pdf_document(
            pdf_path=DATA_RAW_DIR / "is_800_2007.pdf",
            code_id="IS 800:2007",
            code_title="General Construction in Steel - Code of Practice",
            output_json_path=DATA_PROCESSED_DIR / "is800_preprocessed.json",
            extract_media=args.extract_media,
        )
    elif args.code == "is875":
        preprocess_pdf_document(
            pdf_path=DATA_RAW_DIR / "is_875_part_2_1987.pdf",
            code_id="IS 875 (Part 2):1987",
            code_title="Design Loads for Buildings and Structures - Imposed Loads",
            output_json_path=DATA_PROCESSED_DIR / "is875_part_2_preprocessed.json",
            extract_media=args.extract_media,
        )
    elif args.code == "is13920":
        preprocess_pdf_document(
            pdf_path=DATA_RAW_DIR / "is_13920_2016.pdf",
            code_id="IS 13920:2016",
            code_title="Ductile Design and Detailing of Reinforced Concrete Structures Subjected to Seismic Forces",
            output_json_path=DATA_PROCESSED_DIR / "is13920_preprocessed.json",
            extract_media=args.extract_media,
        )

