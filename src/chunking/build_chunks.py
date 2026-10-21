"""
Build unified chunk file (chunks.jsonl) from processed clauses and tables.
Encodes 9 clauses and 2 tables into 11 chunks with clean embedding/retrieval text
and hierarchical context_path.
"""

import json
from pathlib import Path
from src.chunking.schema import ClauseChunk

DATA_DIR = Path("data/processed")
CLAUSES_FILE = DATA_DIR / "is456_cl_26_5_1.json"
TABLE_16_FILE = DATA_DIR / "is456_table_16.json"
TABLE_19_FILE = DATA_DIR / "is456_table_19.json"
OUTPUT_FILE = DATA_DIR / "chunks.jsonl"


def render_table_16(t: dict) -> str:
    lines = [
        f"Table {t['table_number']}: {t['title']}",
        f"(Clause {t['clause_reference']})\n",
        "| Exposure | Nominal Concrete Cover in mm not Less Than |",
        "| --- | --- |",
    ]
    for row in t["rows"]:
        lines.append(f"| {row['exposure']} | {row['nominal_cover_mm']} |")

    lines.append("\nNotes:")
    for idx, note in enumerate(t["notes"], 1):
        lines.append(f"{idx}. {note}")

    return "\n".join(lines)


def render_table_19(t: dict) -> str:
    clause_refs = ", ".join(t["clause_references"])
    lines = [
        f"Table {t['table_number']}: {t['title']}, {t['symbol']}, {t['units']}",
        f"(Clauses {clause_refs})\n",
        f"| {t['row_variable']} | " + " | ".join(t["column_headings"]) + " |",
        "| --- | " + " | ".join(["---"] * len(t["column_headings"])) + " |",
    ]
    for row in t["rows"]:
        vals = [f"{row['tau_c'][g]:.2f}" for g in t["column_headings"]]
        lines.append(f"| {row['pt_label']} | " + " | ".join(vals) + " |")

    lines.append("\nNotes:")
    for idx, note in enumerate(t["notes"], 1):
        lines.append(f"{idx}. {note}")

    return "\n".join(lines)


def get_context_path(clause_number: str) -> str:
    if clause_number in ("26.5.1.1(a)", "26.5.1.1(b)"):
        return (
            "IS 456 > 26.5 Requirements of Reinforcement for Structural Members > "
            "26.5.1 Beams > 26.5.1.1 Tension reinforcement"
        )
    return (
        "IS 456 > 26.5 Requirements of Reinforcement for Structural Members > "
        "26.5.1 Beams"
    )


def build_chunks():
    chunks = []

    # 1. Process 9 clauses
    with open(CLAUSES_FILE, "r", encoding="utf-8") as f:
        clauses_data = json.load(f)

    for c_raw in clauses_data:
        c = ClauseChunk(**c_raw)
        code_prefix = c.code_id.replace(" ", "")
        chunk_id = f"{code_prefix}-{c.edition_year}-CL-{c.clause_number}"
        citation = f"{c.code_id}:{c.edition_year} Cl. {c.clause_number}"

        chunks.append({
            "chunk_id": chunk_id,
            "chunk_type": "clause",
            "code_id": c.code_id,
            "edition_year": c.edition_year,
            "clause_number": c.clause_number,
            "table_number": None,
            "title": c.clause_title,
            "context_path": get_context_path(c.clause_number),
            "page_number": c.page_number,
            "text": c.embedding_text,
            "cross_references": c.cross_references,
            "citation": citation,
            "verified": c.verified,
        })

    # 2. Process Table 16
    with open(TABLE_16_FILE, "r", encoding="utf-8") as f:
        t16 = json.load(f)

    code_prefix_16 = t16["code_id"].replace(" ", "")
    p_num_16 = t16["page_number"]
    chunks.append({
        "chunk_id": f"{code_prefix_16}-{t16['edition_year']}-TABLE-{t16['table_number']}",
        "chunk_type": "table",
        "code_id": t16["code_id"],
        "edition_year": t16["edition_year"],
        "clause_number": None,
        "table_number": t16["table_number"],
        "title": t16["title"],
        "context_path": None,
        "page_number": [p_num_16] if isinstance(p_num_16, int) else p_num_16,
        "text": render_table_16(t16),
        "cross_references": [t16["clause_reference"]],
        "citation": f"{t16['code_id']}:{t16['edition_year']} Table {t16['table_number']}",
        "verified": t16["verified"],
    })

    # 3. Process Table 19
    with open(TABLE_19_FILE, "r", encoding="utf-8") as f:
        t19 = json.load(f)

    code_prefix_19 = t19["code_id"].replace(" ", "")
    p_num_19 = t19["page_number"]
    chunks.append({
        "chunk_id": f"{code_prefix_19}-{t19['edition_year']}-TABLE-{t19['table_number']}",
        "chunk_type": "table",
        "code_id": t19["code_id"],
        "edition_year": t19["edition_year"],
        "clause_number": None,
        "table_number": t19["table_number"],
        "title": t19["title"],
        "context_path": None,
        "page_number": [p_num_19] if isinstance(p_num_19, int) else p_num_19,
        "text": render_table_19(t19),
        "cross_references": t19["clause_references"],
        "citation": f"{t19['code_id']}:{t19['edition_year']} Table {t19['table_number']}",
        "verified": t19["verified"],
    })

    # Write output JSONL
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    print(f"Successfully generated {len(chunks)} chunks to {OUTPUT_FILE}")


if __name__ == "__main__":
    build_chunks()
