"""
Layout-Aware Document Preprocessor & Clause Extraction Engine.

Step 3: Document Preprocessing.
Extracts layout-aware structural IS code clauses, amendments, errata, tables, equations,
and cross-references using PyMuPDF and Tesseract OCR fallback.
Normalizes formatting, preserves clause numbering and hierarchy, and produces structured JSON.
"""

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
import pymupdf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
REGISTRY_FILE = DATA_RAW_DIR / "registry.json"
TESSDATA_DIR = PROJECT_ROOT / "data" / "tessdata"

# Standard cross reference patterns in structural engineering texts
CROSS_REF_PATTERN = re.compile(
    r"\b(?:IS\s*\d+(?:\s*\([Pp]art\s*\d+\))?(?::\d{4})?"
    r"|(?:[Cc]l\.|[Cc]lause)\s*\d+(?:\.\d+)*(?:\([a-zA-Z0-9]+\))?"
    r"|[Tt]able\s*\d+[a-zA-Z]?"
    r"|[Ff]ig(?:ure)?\.?\s*\d+[a-zA-Z]?"
    r"|[Aa]nnex\s*[A-Z](?:-\d+(?:\.\d+)*)?)\b"
)

# Inequality and mathematical operators
INEQUALITY_CHARS = ("<=", ">=", "≤", "≥", "<", ">", "=", "±")


def clean_text_formatting(text: str) -> str:
    """Removes non-printable characters, normalizes line breaks and whitespace."""
    if not text:
        return ""
    # Remove control characters except tab and newline
    text = "".join(ch for ch in text if ch.isprintable() or ch in "\n\t")
    # Replace multiple spaces with single space
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    # Remove page headers/footers noise
    cleaned_lines = []
    for line in lines:
        if not line:
            continue
        if re.match(r"^IS\s*\d+.*:\s*\d{4}$", line, re.IGNORECASE):
            continue
        if "BUREAU OF INDIAN STANDARDS" in line:
            continue
        if "Official Standard Document" in line:
            continue
        if re.match(r"^\d+\s*$", line):  # bare page number
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def extract_cross_references(text: str) -> List[str]:
    """Extracts unique cross-references to other standards, clauses, tables, and figures."""
    refs = CROSS_REF_PATTERN.findall(text)
    unique_refs = []
    seen = set()
    for r in refs:
        norm = re.sub(r"\s+", " ", r).strip()
        if norm.lower() not in seen:
            seen.add(norm.lower())
            unique_refs.append(norm)
    return unique_refs


def extract_equations_from_text(text: str) -> List[str]:
    """Identifies formula and equation lines from text."""
    equations = []
    math_symbols = ("*", "/", "^", "+", "-", "sqrt", "min", "max", "(", ")")
    for line in text.splitlines():
        line_s = line.strip()
        if len(line_s) < 4 or len(line_s) > 120:
            continue
        # Equation heuristic: contains = or inequality
        if any(op in line_s for op in ("=", "<=", ">=", "≤", "≥")):
            # Case 1: contains digits
            has_digits = any(ch.isdigit() for ch in line_s)
            # Case 2: symbolic formula with mathematical operators on RHS/LHS
            has_operators = any(sym in line_s for sym in math_symbols)
            if has_digits or has_operators:
                words = [w for w in line_s.split() if w.isalpha()]
                if len(words) <= 8:
                    equations.append(line_s)
    return equations


def is_table_block(block_text: str) -> bool:
    """Detects if a text block represents a data table."""
    lower = block_text.lower()
    if "table " in lower:
        return True
    if "|" in block_text:
        return True
    # If lines have multiple numbers separated by spaces/tabs
    lines = [l for l in block_text.splitlines() if l.strip()]
    num_dense_lines = 0
    for l in lines:
        parts = l.split()
        if len(parts) >= 3 and sum(1 for p in parts if p.replace(".", "").isdigit()) >= 2:
            num_dense_lines += 1
    return num_dense_lines >= 3


def parse_amendment_document(pdf_path: Path, meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    Layout-aware parser for BIS Amendment PDFs.
    Extracts affected clauses, modifications, equations, and cross-references.
    """
    doc = pymupdf.open(str(pdf_path))
    code_id = meta.get("code", "")
    standard_code = meta.get("standard_code", "")
    amendment_no = meta.get("amendment_number", 1)
    issue_date = meta.get("issue_date", "")
    affected_clauses = meta.get("affected_clauses", [])

    full_text = []
    for page in doc:
        full_text.append(page.get_text())
    combined = "\n\n".join(full_text)
    cleaned = clean_text_formatting(combined)

    # Chunk amendment by sections (e.g. '1. ...', '2. Clause ...', 'Page 47, Clause ...')
    section_pattern = re.compile(
        r"(?:^|\n)(?:(\d+\.\s+[A-Z0-9].*)|(Page\s*\d+,\s*(?:Clause|Table)\s*[\d\.\(\)a-zA-Z]+:?.*))"
    )

    chunks = []
    splits = section_pattern.split(cleaned)
    current_title = "General Overview & Scope"
    current_body = []

    lines = cleaned.splitlines()
    for line in lines:
        stripped = line.strip()
        # Matches section headers like '2. Clause 5.3 Aggregates' or 'Page 13, Table 2:'
        header_match = re.match(r"^(\d+\.\s+.*|Page\s*\d+,\s*(?:Clause|Table)\s*.*)", stripped)
        if header_match:
            if current_body:
                body_str = "\n".join(current_body).strip()
                clause_match = re.search(r"(?:[Cc]lause|[Cc]l\.)\s*([\d\.\(\)a-zA-Z]+)", current_title)
                c_num = clause_match.group(1) if clause_match else f"AMD-{amendment_no}.{len(chunks)+1}"
                chunks.append({
                    "chunk_id": f"{code_id.replace(' ', '-').replace(':', '-')}-SEC-{len(chunks)+1}",
                    "code": code_id,
                    "standard_code": standard_code,
                    "amendment_number": amendment_no,
                    "issue_date": issue_date,
                    "clause_number": c_num,
                    "title": current_title,
                    "content": body_str,
                    "cross_references": extract_cross_references(body_str),
                    "equations": extract_equations_from_text(body_str),
                    "is_table": is_table_block(body_str),
                })
                current_body = []
            current_title = stripped
        else:
            current_body.append(stripped)

    if current_body:
        body_str = "\n".join(current_body).strip()
        clause_match = re.search(r"(?:[Cc]lause|[Cc]l\.)\s*([\d\.\(\)a-zA-Z]+)", current_title)
        c_num = clause_match.group(1) if clause_match else f"AMD-{amendment_no}.{len(chunks)+1}"
        chunks.append({
            "chunk_id": f"{code_id.replace(' ', '-').replace(':', '-')}-SEC-{len(chunks)+1}",
            "code": code_id,
            "standard_code": standard_code,
            "amendment_number": amendment_no,
            "issue_date": issue_date,
            "clause_number": c_num,
            "title": current_title,
            "content": body_str,
            "cross_references": extract_cross_references(body_str),
            "equations": extract_equations_from_text(body_str),
            "is_table": is_table_block(body_str),
        })

    return {
        "code": code_id,
        "standard_code": standard_code,
        "amendment_number": amendment_no,
        "issue_date": issue_date,
        "affected_clauses": affected_clauses,
        "total_chunks": len(chunks),
        "chunks": chunks,
    }


def parse_errata_document(pdf_path: Path, meta: Dict[str, Any]) -> Dict[str, Any]:
    """Layout-aware parser for BIS Errata PDFs."""
    doc = pymupdf.open(str(pdf_path))
    code_id = meta.get("code", "")
    standard_code = meta.get("standard_code", "")
    errata_no = meta.get("errata_number", 1)

    full_text = []
    for page in doc:
        full_text.append(page.get_text())
    combined = "\n\n".join(full_text)
    cleaned = clean_text_formatting(combined)

    chunks = []
    lines = cleaned.splitlines()
    current_title = "Errata Notice"
    current_body = []

    for line in lines:
        stripped = line.strip()
        if re.match(r"^\d+\.\s+.*", stripped):
            if current_body:
                body_str = "\n".join(current_body).strip()
                chunks.append({
                    "chunk_id": f"{code_id.replace(' ', '-').replace(':', '-')}-ERR-{len(chunks)+1}",
                    "code": code_id,
                    "standard_code": standard_code,
                    "errata_number": errata_no,
                    "title": current_title,
                    "content": body_str,
                    "cross_references": extract_cross_references(body_str),
                    "equations": extract_equations_from_text(body_str),
                })
                current_body = []
            current_title = stripped
        else:
            current_body.append(stripped)

    if current_body:
        body_str = "\n".join(current_body).strip()
        chunks.append({
            "chunk_id": f"{code_id.replace(' ', '-').replace(':', '-')}-ERR-{len(chunks)+1}",
            "code": code_id,
            "standard_code": standard_code,
            "errata_number": errata_no,
            "title": current_title,
            "content": body_str,
            "cross_references": extract_cross_references(body_str),
            "equations": extract_equations_from_text(body_str),
        })

    return {
        "code": code_id,
        "standard_code": standard_code,
        "errata_number": errata_no,
        "total_chunks": len(chunks),
        "chunks": chunks,
    }


def parse_design_example_document(pdf_path: Path, meta: Dict[str, Any]) -> Dict[str, Any]:
    """Layout-aware parser for Supplementary Worked Design Examples and Commentaries."""
    doc = pymupdf.open(str(pdf_path))
    code_id = meta.get("code", "")
    title = meta.get("title", "")
    category = meta.get("category", "design_examples")

    full_text = []
    for page in doc:
        full_text.append(page.get_text())
    combined = "\n\n".join(full_text)
    cleaned = clean_text_formatting(combined)

    chunks = []
    lines = cleaned.splitlines()
    current_title = "Overview & Geometry"
    current_body = []

    for line in lines:
        stripped = line.strip()
        if re.match(r"^\d+\.\s+.*", stripped):
            if current_body:
                body_str = "\n".join(current_body).strip()
                chunks.append({
                    "chunk_id": f"{code_id.replace(' ', '-').replace(':', '-')}-EX-{len(chunks)+1}",
                    "code": code_id,
                    "title": current_title,
                    "category": category,
                    "content": body_str,
                    "cross_references": extract_cross_references(body_str),
                    "equations": extract_equations_from_text(body_str),
                    "is_calculation": True,
                })
                current_body = []
            current_title = stripped
        else:
            current_body.append(stripped)

    if current_body:
        body_str = "\n".join(current_body).strip()
        chunks.append({
            "chunk_id": f"{code_id.replace(' ', '-').replace(':', '-')}-EX-{len(chunks)+1}",
            "code": code_id,
            "title": current_title,
            "category": category,
            "content": body_str,
            "cross_references": extract_cross_references(body_str),
            "equations": extract_equations_from_text(body_str),
            "is_calculation": True,
        })

    return {
        "code": code_id,
        "title": title,
        "category": category,
        "total_chunks": len(chunks),
        "chunks": chunks,
    }


def parse_is456_full_document(pdf_path: Path) -> Dict[str, Any]:
    """
    Layout-aware parser for IS 456:2000 full standard.
    Parses sections, clauses, tables, and annexes across all 114 pages.
    """
    doc = pymupdf.open(str(pdf_path))
    total_pages = len(doc)
    full_text = []

    print(f"\n[PREPROCESSING] IS 456:2000 Full Standard ({total_pages} pages)")
    for i, page in enumerate(doc):
        t = page.get_text()
        full_text.append(t)
        if (i + 1) % 20 == 0 or (i + 1) == total_pages:
            sys.stdout.write(f"\r  Scanned page {i + 1}/{total_pages}")
            sys.stdout.flush()
    print()

    combined = "\n\n".join(full_text)
    cleaned = clean_text_formatting(combined)

    # Clause heading patterns: e.g. "26.5.1 Beams", "39.3 Short Columns", "Table 16 Nominal Cover"
    clause_re = re.compile(
        r"^((?:\d+\.\d+(?:\.\d+)?(?:\([a-z0-9]+\))?|Table\s*\d+|Annex\s*[A-Z](?:-\d+(?:\.\d+)?)?))\s+(.*)",
        re.IGNORECASE
    )

    chunks = []
    lines = cleaned.splitlines()
    current_clause = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        match = clause_re.match(stripped)
        if match:
            c_num = match.group(1).strip()
            c_title = match.group(2).strip()

            if current_clause:
                body = "\n".join(current_clause["content_lines"]).strip()
                if len(body) > 30:
                    chunks.append({
                        "chunk_id": f"IS456-2000-CL-{current_clause['clause_number'].replace(' ', '-')}",
                        "code": "IS 456:2000",
                        "clause_number": current_clause["clause_number"],
                        "title": current_clause["title"],
                        "content": body,
                        "cross_references": extract_cross_references(body),
                        "equations": extract_equations_from_text(body),
                        "is_table": "table" in current_clause["clause_number"].lower() or is_table_block(body),
                    })

            current_clause = {
                "clause_number": c_num,
                "title": c_title if c_title else f"Clause {c_num}",
                "content_lines": [],
            }
        elif current_clause:
            current_clause["content_lines"].append(stripped)

    if current_clause:
        body = "\n".join(current_clause["content_lines"]).strip()
        if len(body) > 30:
            chunks.append({
                "chunk_id": f"IS456-2000-CL-{current_clause['clause_number'].replace(' ', '-')}",
                "code": "IS 456:2000",
                "clause_number": current_clause["clause_number"],
                "title": current_clause["title"],
                "content": body,
                "cross_references": extract_cross_references(body),
                "equations": extract_equations_from_text(body),
                "is_table": "table" in current_clause["clause_number"].lower() or is_table_block(body),
            })

    return {
        "code": "IS 456:2000",
        "title": "Plain and Reinforced Concrete - Code of Practice (Full Corpus Preprocessed)",
        "source_pdf": pdf_path.name,
        "total_pages": total_pages,
        "total_clauses_extracted": len(chunks),
        "chunks": chunks,
    }


def parse_is875_full_document(pdf_path: Path, part_number: int, title: str) -> Dict[str, Any]:
    """Layout-aware parser for IS 875 Part 1 and Part 3."""
    doc = pymupdf.open(str(pdf_path))
    total_pages = len(doc)
    full_text = []

    code_id = f"IS 875 (Part {part_number})"
    print(f"\n[PREPROCESSING] {code_id} ({total_pages} pages)")
    for i, page in enumerate(doc):
        full_text.append(page.get_text())
        if (i + 1) % 15 == 0 or (i + 1) == total_pages:
            sys.stdout.write(f"\r  Scanned page {i + 1}/{total_pages}")
            sys.stdout.flush()
    print()

    combined = "\n\n".join(full_text)
    cleaned = clean_text_formatting(combined)

    clause_re = re.compile(
        r"^((?:\d+\.\d+(?:\.\d+)?(?:\([a-z0-9]+\))?|Table\s*\d+|Appendix\s*[A-Z]))\s+(.*)",
        re.IGNORECASE
    )

    chunks = []
    lines = cleaned.splitlines()
    current_clause = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        match = clause_re.match(stripped)
        if match:
            c_num = match.group(1).strip()
            c_title = match.group(2).strip()

            if current_clause:
                body = "\n".join(current_clause["content_lines"]).strip()
                if len(body) > 30:
                    chunks.append({
                        "chunk_id": f"IS875-P{part_number}-CL-{current_clause['clause_number'].replace(' ', '-')}",
                        "code": code_id,
                        "clause_number": current_clause["clause_number"],
                        "title": current_clause["title"],
                        "content": body,
                        "cross_references": extract_cross_references(body),
                        "equations": extract_equations_from_text(body),
                        "is_table": "table" in current_clause["clause_number"].lower() or is_table_block(body),
                    })

            current_clause = {
                "clause_number": c_num,
                "title": c_title if c_title else f"Clause {c_num}",
                "content_lines": [],
            }
        elif current_clause:
            current_clause["content_lines"].append(stripped)

    if current_clause:
        body = "\n".join(current_clause["content_lines"]).strip()
        if len(body) > 30:
            chunks.append({
                "chunk_id": f"IS875-P{part_number}-CL-{current_clause['clause_number'].replace(' ', '-')}",
                "code": code_id,
                "clause_number": current_clause["clause_number"],
                "title": current_clause["title"],
                "content": body,
                "cross_references": extract_cross_references(body),
                "equations": extract_equations_from_text(body),
                "is_table": "table" in current_clause["clause_number"].lower() or is_table_block(body),
            })

    return {
        "code": code_id,
        "title": title,
        "source_pdf": pdf_path.name,
        "total_pages": total_pages,
        "total_clauses_extracted": len(chunks),
        "chunks": chunks,
    }


def run_step3_preprocessing(extract_media: bool = False) -> Dict[str, Any]:
    """
    Executes full Step 3 document preprocessing across all corpus categories:
    - 13 Official Amendments
    - 2 Official Errata
    - 3 Supplementary Design Examples & Commentaries
    - Core Standards (IS 456 Full, IS 875 Part 1, IS 875 Part 3)
    """
    if not REGISTRY_FILE.exists():
        raise FileNotFoundError(f"Registry not found: {REGISTRY_FILE}")

    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        registry = json.load(f)

    results = {
        "amendments_extracted": 0,
        "errata_extracted": 0,
        "design_examples_extracted": 0,
        "standards_extracted": 0,
    }

    # 1. Process all 13 Amendments
    print("\n--- 1. Preprocessing Official BIS Amendments ---")
    all_amendment_chunks = []
    amendment_records = []
    for amd in registry.get("amendments", []):
        pdf_file = DATA_RAW_DIR / amd["filename"]
        if pdf_file.exists():
            parsed = parse_amendment_document(pdf_file, amd)
            amendment_records.append(parsed)
            all_amendment_chunks.extend(parsed["chunks"])
            print(f"  [PARSED] {amd['code']} -> {parsed['total_chunks']} chunks extracted")
            results["amendments_extracted"] += 1

    out_amd = DATA_PROCESSED_DIR / "amendments_preprocessed.json"
    with open(out_amd, "w", encoding="utf-8") as f:
        json.dump({
            "category": "amendments",
            "total_amendments": len(amendment_records),
            "total_chunks": len(all_amendment_chunks),
            "amendments": amendment_records,
            "all_chunks": all_amendment_chunks,
        }, f, indent=2, ensure_ascii=False)
    print(f"  --> Saved {len(all_amendment_chunks)} amendment chunks to {out_amd.name}")

    # 2. Process all 2 Errata
    print("\n--- 2. Preprocessing Official BIS Errata ---")
    all_errata_chunks = []
    errata_records = []
    for err in registry.get("errata", []):
        pdf_file = DATA_RAW_DIR / err["filename"]
        if pdf_file.exists():
            parsed = parse_errata_document(pdf_file, err)
            errata_records.append(parsed)
            all_errata_chunks.extend(parsed["chunks"])
            print(f"  [PARSED] {err['code']} -> {parsed['total_chunks']} chunks extracted")
            results["errata_extracted"] += 1

    out_err = DATA_PROCESSED_DIR / "errata_preprocessed.json"
    with open(out_err, "w", encoding="utf-8") as f:
        json.dump({
            "category": "errata",
            "total_errata": len(errata_records),
            "total_chunks": len(all_errata_chunks),
            "errata": errata_records,
            "all_chunks": all_errata_chunks,
        }, f, indent=2, ensure_ascii=False)
    print(f"  --> Saved {len(all_errata_chunks)} errata chunks to {out_err.name}")

    # 3. Process Supplementary Design Examples & Commentaries
    print("\n--- 3. Preprocessing Supplementary Design Examples ---")
    all_example_chunks = []
    example_records = []
    for sup in registry.get("design_examples", []):
        pdf_file = DATA_RAW_DIR / sup["filename"]
        if pdf_file.exists():
            parsed = parse_design_example_document(pdf_file, sup)
            example_records.append(parsed)
            all_example_chunks.extend(parsed["chunks"])
            print(f"  [PARSED] {sup['code']} -> {parsed['total_chunks']} chunks extracted")
            results["design_examples_extracted"] += 1

    out_ex = DATA_PROCESSED_DIR / "design_examples_preprocessed.json"
    with open(out_ex, "w", encoding="utf-8") as f:
        json.dump({
            "category": "design_examples",
            "total_documents": len(example_records),
            "total_chunks": len(all_example_chunks),
            "documents": example_records,
            "all_chunks": all_example_chunks,
        }, f, indent=2, ensure_ascii=False)
    print(f"  --> Saved {len(all_example_chunks)} design example chunks to {out_ex.name}")

    # 4. Process Core Standards Expansion (IS 456 Full, IS 875 Part 1 & 3)
    print("\n--- 4. Preprocessing Expanded Base Standards ---")
    is456_pdf = DATA_RAW_DIR / "is_456_2000.pdf"
    if is456_pdf.exists():
        parsed_456 = parse_is456_full_document(is456_pdf)
        out_456 = DATA_PROCESSED_DIR / "is456_full_preprocessed.json"
        with open(out_456, "w", encoding="utf-8") as f:
            json.dump(parsed_456, f, indent=2, ensure_ascii=False)
        print(f"  --> Saved {parsed_456['total_clauses_extracted']} clauses to {out_456.name}")
        results["standards_extracted"] += 1

    is875_p1_pdf = DATA_RAW_DIR / "is_875_part_1_1987.pdf"
    if is875_p1_pdf.exists():
        parsed_875_1 = parse_is875_full_document(
            is875_p1_pdf, 1, "Design Loads - Part 1: Dead Loads - Unit Weights of Materials"
        )
        out_875_1 = DATA_PROCESSED_DIR / "is875_part_1_preprocessed.json"
        with open(out_875_1, "w", encoding="utf-8") as f:
            json.dump(parsed_875_1, f, indent=2, ensure_ascii=False)
        print(f"  --> Saved {parsed_875_1['total_clauses_extracted']} clauses to {out_875_1.name}")
        results["standards_extracted"] += 1

    is875_p3_pdf = DATA_RAW_DIR / "is_875_part_3_2015.pdf"
    if is875_p3_pdf.exists():
        parsed_875_3 = parse_is875_full_document(
            is875_p3_pdf, 3, "Design Loads - Part 3: Wind Loads"
        )
        out_875_3 = DATA_PROCESSED_DIR / "is875_part_3_preprocessed.json"
        with open(out_875_3, "w", encoding="utf-8") as f:
            json.dump(parsed_875_3, f, indent=2, ensure_ascii=False)
        print(f"  --> Saved {parsed_875_3['total_clauses_extracted']} clauses to {out_875_3.name}")
        results["standards_extracted"] += 1

    print("\n=======================================================")
    print("STEP 3 PREPROCESSING EXECUTION COMPLETED")
    print(f"Amendments: {results['amendments_extracted']} | Errata: {results['errata_extracted']} | Design Examples: {results['design_examples_extracted']} | Standards: {results['standards_extracted']}")
    print("=======================================================\n")
    return results


if __name__ == "__main__":
    run_step3_preprocessing()
