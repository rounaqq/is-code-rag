"""
Compile and Enrich Multi-Standard Chunks with Step 4 Metadata.

Step 4: Chunking & Metadata Enrichment.
Consolidates clauses, tables, amendments, errata, and worked design examples
across the complete corpus into unified metadata-enriched JSON Lines:
- data/processed/all_enriched_chunks.jsonl

Enforces:
- Clause-level granularity
- Dedicated chunk types: 'clause', 'table', 'amendment', 'errata', 'example'
- Complete metadata payload:
  * IS code number
  * Year / edition
  * Amendment
  * Section
  * Clause number
  * Title
  * Applicability
  * Keywords
  * Dependencies
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Set

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_FILE = DATA_PROCESSED_DIR / "all_enriched_chunks.jsonl"


def get_section_from_clause(clause_num: str, code: str) -> str:
    """Infers structural section from clause number hierarchy."""
    c_str = str(clause_num).strip().lower()
    if "is 456" in code.lower():
        if c_str.startswith("1") and not c_str.startswith("18") and not c_str.startswith("19"):
            return "Section 2 Materials, Workmanship, Inspection & Testing"
        elif c_str.startswith("18") or c_str.startswith("19") or c_str.startswith("20") or c_str.startswith("21") or c_str.startswith("22") or c_str.startswith("23") or c_str.startswith("24") or c_str.startswith("25") or c_str.startswith("26"):
            return "Section 3 General Design Considerations"
        elif c_str.startswith("28") or c_str.startswith("29") or c_str.startswith("30") or c_str.startswith("31") or c_str.startswith("32") or c_str.startswith("33") or c_str.startswith("34"):
            return "Section 4 Special Design Requirements for Structural Members and Systems"
        elif c_str.startswith("35") or c_str.startswith("36") or c_str.startswith("37") or c_str.startswith("38") or c_str.startswith("39") or c_str.startswith("40") or c_str.startswith("41") or c_str.startswith("42") or c_str.startswith("43"):
            return "Section 5 Structural Design (Limit State Method)"
        elif "annex" in c_str or "g-" in c_str:
            return "Annexures (Method of Analysis & Design Formulas)"
        elif "table 16" in c_str:
            return "Durability Requirements (Table 16)"
        elif "table 19" in c_str or "table 20" in c_str:
            return "Limit State of Collapse: Shear (Tables 19 & 20)"
        return "General Structural Concrete Provisions"

    elif "13920" in code:
        if c_str.startswith("5"):
            return "General Detailing Requirements & Materials"
        elif c_str.startswith("6"):
            return "Beams (Flexural Ductility & Confinement)"
        elif c_str.startswith("7"):
            return "Columns & Frame Members Under Axial & Bending"
        elif c_str.startswith("8"):
            return "Beam-Column Joints of Frame Structures"
        elif c_str.startswith("9"):
            return "Special Structural Walls (Shear Walls)"
        return "Seismic Ductile Detailing Provisions"

    elif "1893" in code:
        if c_str.startswith("6"):
            return "General Principles and Criteria for Earthquake Resistant Design"
        elif c_str.startswith("7"):
            return "Design Criteria for Multi-Storey Buildings (Base Shear & Drift)"
        return "Earthquake Resistant Design of Structures"

    elif "800" in code:
        if c_str.startswith("6"):
            return "Section 6 Design of Tension Members"
        elif c_str.startswith("7"):
            return "Section 7 Design of Compression Members"
        elif c_str.startswith("8"):
            return "Section 8 Design of Members Subjected to Bending"
        elif c_str.startswith("10"):
            return "Section 10 Design of Connections (Bolted & Welded)"
        return "Structural Steel Design Provisions"

    elif "875" in code:
        if "part 1" in code.lower():
            return "Dead Loads: Unit Weights of Building Materials"
        elif "part 2" in code.lower():
            return "Imposed / Live Loads for Occupancies"
        elif "part 3" in code.lower():
            return "Wind Loads: Basic Wind Speed & Design Pressure"

    return "Structural Engineering Provisions"


def get_applicability(code: str, title: str) -> str:
    """Determines structural component or engineering domain applicability."""
    t_lower = title.lower()
    if "beam" in t_lower:
        return "RC Beams (Flexure, Shear & Deflection)"
    elif "column" in t_lower:
        return "RC Columns (Axial Compression, Slenderness & Ties)"
    elif "slab" in t_lower:
        return "RC Slabs (One-Way & Two-Way Bending)"
    elif "footing" in t_lower:
        return "RC Isolated Footings (Soil Bearing & Punching Shear)"
    elif "13920" in code:
        return "Seismic Ductile Detailing in Zones III, IV, and V"
    elif "1893" in code:
        return "Seismic Hazard Analysis & Base Shear Computation"
    elif "800" in code:
        return "Structural Steel Frames, Connections & Trusses"
    elif "875" in code:
        return "Design Loads Evaluation (Gravity & Wind)"
    return "Structural Civil Engineering Design"


def compile_all_enriched_chunks() -> List[Dict[str, Any]]:
    """Compiles all verified clauses, standards, amendments, and design examples into enriched chunks."""
    all_chunks: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()

    # 1. Base IS 456 Curated Chunks (23 human-verified chunks)
    curated_path = DATA_PROCESSED_DIR / "chunks.jsonl"
    if curated_path.exists():
        with open(curated_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                c = json.loads(line)
                cid = c.get("chunk_id")
                if cid and cid not in seen_ids:
                    seen_ids.add(cid)
                    c_num = str(c.get("clause_number") or c.get("table_number") or "")
                    is_table = "table" in cid.lower()
                    chunk = {
                        "chunk_id": cid,
                        "code": "IS 456:2000",
                        "year": 2000,
                        "amendment": "Base Standard (Incorporating Amd 1 & 2)",
                        "section": get_section_from_clause(c_num, "IS 456:2000"),
                        "clause_number": c_num,
                        "title": c.get("title", ""),
                        "applicability": get_applicability("IS 456:2000", c.get("title", "")),
                        "keywords": [
                            "IS 456:2000",
                            f"Cl. {c_num}",
                            c.get("title", ""),
                            "Reinforced Concrete",
                        ],
                        "dependencies": ["IS 456:2000"],
                        "chunk_type": "table" if is_table else "clause",
                        "text": c.get("text", f"{c.get('title')}: {c.get('text', '')}"),
                        "cross_references": c.get("cross_references", []),
                        "equations": [c.get("formula_verified")] if c.get("formula_verified") else [],
                        "verified": True,
                        "metadata": {
                            "source_file": "chunks.jsonl",
                            "page_number": c.get("page_number", []),
                        },
                    }
                    all_chunks.append(chunk)

    # 2. Official Amendments (13 documents, 59 chunks)
    amd_path = DATA_PROCESSED_DIR / "amendments_preprocessed.json"
    if amd_path.exists():
        with open(amd_path, "r", encoding="utf-8") as f:
            amd_data = json.load(f)
        for c in amd_data.get("all_chunks", []):
            cid = c.get("chunk_id")
            if cid and cid not in seen_ids:
                seen_ids.add(cid)
                std_code = c.get("standard_code", "IS 456:2000")
                chunk = {
                    "chunk_id": cid,
                    "code": c.get("code", std_code),
                    "year": int(c.get("issue_date", "2001").split()[-1]) if any(ch.isdigit() for ch in c.get("issue_date", "")) else 2001,
                    "amendment": f"Amendment No. {c.get('amendment_number')} ({c.get('issue_date')})",
                    "section": f"Amendment to {std_code} (Published by BIS)",
                    "clause_number": c.get("clause_number", ""),
                    "title": c.get("title", ""),
                    "applicability": f"Official BIS Amendment to {std_code}",
                    "keywords": [
                        std_code,
                        f"Amendment {c.get('amendment_number')}",
                        c.get("title", ""),
                    ],
                    "dependencies": [std_code],
                    "chunk_type": "amendment",
                    "text": f"{c.get('title')}\n{c.get('content')}",
                    "cross_references": c.get("cross_references", []),
                    "equations": c.get("equations", []),
                    "verified": True,
                    "metadata": {
                        "issue_date": c.get("issue_date"),
                        "amendment_number": c.get("amendment_number"),
                        "is_table": c.get("is_table", False),
                    },
                }
                all_chunks.append(chunk)

    # 3. Official Errata (2 documents, 7 chunks)
    err_path = DATA_PROCESSED_DIR / "errata_preprocessed.json"
    if err_path.exists():
        with open(err_path, "r", encoding="utf-8") as f:
            err_data = json.load(f)
        for c in err_data.get("all_chunks", []):
            cid = c.get("chunk_id")
            if cid and cid not in seen_ids:
                seen_ids.add(cid)
                std_code = c.get("standard_code", "IS 456:2000")
                chunk = {
                    "chunk_id": cid,
                    "code": c.get("code", std_code),
                    "year": 2000 if "456" in std_code else 2007,
                    "amendment": f"Errata No. {c.get('errata_number')}",
                    "section": f"Official Printing Errata for {std_code}",
                    "clause_number": f"ERR-{c.get('errata_number')}",
                    "title": c.get("title", ""),
                    "applicability": f"Typographical Correction for {std_code}",
                    "keywords": [std_code, "Errata", c.get("title", "")],
                    "dependencies": [std_code],
                    "chunk_type": "errata",
                    "text": f"{c.get('title')}\n{c.get('content')}",
                    "cross_references": c.get("cross_references", []),
                    "equations": c.get("equations", []),
                    "verified": True,
                    "metadata": {"errata_number": c.get("errata_number")},
                }
                all_chunks.append(chunk)

    # 4. Supplementary Design Examples (3 documents, 13 chunks)
    ex_path = DATA_PROCESSED_DIR / "design_examples_preprocessed.json"
    if ex_path.exists():
        with open(ex_path, "r", encoding="utf-8") as f:
            ex_data = json.load(f)
        for c in ex_data.get("all_chunks", []):
            cid = c.get("chunk_id")
            if cid and cid not in seen_ids:
                seen_ids.add(cid)
                chunk = {
                    "chunk_id": cid,
                    "code": c.get("code", "Design Example"),
                    "year": 2016 if "IITK" in c.get("code", "") else 1980,
                    "amendment": None,
                    "section": f"Worked Engineering Design Example ({c.get('code')})",
                    "clause_number": cid.split("-")[-1],
                    "title": c.get("title", ""),
                    "applicability": "Worked Design Example & Structural Engineering Commentary",
                    "keywords": [c.get("code", ""), "Design Example", c.get("title", "")],
                    "dependencies": ["IS 1893:2016", "IS 13920:2016", "IS 456:2000"],
                    "chunk_type": "example",
                    "text": f"{c.get('title')}\n{c.get('content')}",
                    "cross_references": c.get("cross_references", []),
                    "equations": c.get("equations", []),
                    "verified": True,
                    "metadata": {"is_calculation": True},
                }
                all_chunks.append(chunk)

    # 5. Helper for all other preprocessed standard JSON files
    def ingest_preprocessed_file(file_path: Path, code_id: str, default_year: int, std_title: str):
        if not file_path.exists():
            return
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for c in data.get("chunks", []):
            cid = c.get("chunk_id")
            if not cid:
                c_num = str(c.get("clause_number", "")).replace(" ", "-")
                cid = f"{code_id.replace(' ', '-').replace(':', '-')}-CL-{c_num}"
            if cid and cid not in seen_ids:
                seen_ids.add(cid)
                c_num = str(c.get("clause_number", ""))
                is_tbl = c.get("is_table", False) or "table" in c_num.lower()
                chunk = {
                    "chunk_id": cid,
                    "code": code_id,
                    "year": default_year,
                    "amendment": "Base Standard",
                    "section": get_section_from_clause(c_num, code_id),
                    "clause_number": c_num,
                    "title": c.get("title", f"Clause {c_num}"),
                    "applicability": get_applicability(code_id, c.get("title", "")),
                    "keywords": [code_id, f"Clause {c_num}", c.get("title", "")],
                    "dependencies": [code_id],
                    "chunk_type": "table" if is_tbl else "clause",
                    "text": c.get("text") or f"{code_id} Clause {c_num} - {c.get('title')}\n{c.get('content', '')}",
                    "cross_references": c.get("cross_references", []),
                    "equations": c.get("equations", []),
                    "verified": False,
                    "metadata": {
                        "raw_content": c.get("content", c.get("raw_content", "")),
                    },
                }
                all_chunks.append(chunk)

    # Preprocessed standards
    ingest_preprocessed_file(DATA_PROCESSED_DIR / "is13920_preprocessed.json", "IS 13920:2016", 2016, "Ductile Detailing")
    ingest_preprocessed_file(DATA_PROCESSED_DIR / "is1893_part_1_preprocessed.json", "IS 1893 (Part 1):2016", 2016, "Earthquake Resistant Design")
    ingest_preprocessed_file(DATA_PROCESSED_DIR / "is800_preprocessed.json", "IS 800:2007", 2007, "Structural Steel")
    ingest_preprocessed_file(DATA_PROCESSED_DIR / "is875_part_2_preprocessed.json", "IS 875 (Part 2):1987", 1987, "Imposed Loads")
    ingest_preprocessed_file(DATA_PROCESSED_DIR / "is875_part_1_preprocessed.json", "IS 875 (Part 1):1987", 1987, "Dead Loads")
    ingest_preprocessed_file(DATA_PROCESSED_DIR / "is875_part_3_preprocessed.json", "IS 875 (Part 3):2015", 2015, "Wind Loads")
    ingest_preprocessed_file(DATA_PROCESSED_DIR / "is456_full_preprocessed.json", "IS 456:2000", 2000, "Concrete Design Full Standard")

    # Save unified JSON lines
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for chunk in all_chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    print(f"\n[SUCCESS] Compiled {len(all_chunks)} metadata-enriched chunks into {OUTPUT_FILE.name}")
    return all_chunks


if __name__ == "__main__":
    compile_all_enriched_chunks()

