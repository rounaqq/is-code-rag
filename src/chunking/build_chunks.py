"""
Build unified chunk file (chunks.jsonl) from processed clauses and tables.
Encodes verified clauses and tables from IS 456 into 23 chunks with clean
embedding/retrieval text and hierarchical context_path.
"""

import json
from pathlib import Path
from src.chunking.schema import ClauseChunk

DATA_DIR = Path("data/processed")
CLAUSES_FILE = DATA_DIR / "is456_cl_26_5_1.json"
TABLE_16_FILE = DATA_DIR / "is456_table_16.json"
TABLE_19_FILE = DATA_DIR / "is456_table_19.json"
TABLE_20_FILE = DATA_DIR / "is456_table_20.json"
TABLE_XU_MAX_FILE = DATA_DIR / "is456_xu_max_table.json"
ANNEX_G_FILE = DATA_DIR / "is456_annex_g.json"
CL_40_FILE = DATA_DIR / "is456_cl_40.json"

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


def render_table_20(t: dict) -> str:
    clause_refs = ", ".join(t.get("clause_references", []))
    lines = [
        f"Table {t['table_number']}: {t['title']}, {t.get('symbol', 'tau_c_max')}, {t.get('units', 'N/mm2')}",
        f"(Clauses {clause_refs})\n",
        "| Concrete Grade | Maximum Shear Stress tau_c_max (N/mm2) |",
        "| --- | --- |",
    ]
    for row in t["rows"]:
        lines.append(f"| {row['grade']} | {float(row['tau_c_max']):.1f} |")

    return "\n".join(lines)


def render_xu_max_table(t: dict) -> str:
    lines = [
        f"Clause {t['clause_reference']} Note: {t['title']}",
        "| Steel Grade (fy N/mm2) | xu,max / d |",
        "| --- | --- |",
    ]
    for row in t["rows"]:
        lines.append(f"| Fe {row['fy_N_per_mm2']} | {row['xu_max_over_d']} |")

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

    # 1. Process 9 clauses from Clause 26.5.1 (kept exactly as they are)
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

    # 2. Process Table 16 (kept exactly as it is)
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

    # 3. Process Table 19 (kept exactly as it is)
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

    # 4. Process Table 20 (1 chunk)
    with open(TABLE_20_FILE, "r", encoding="utf-8") as f:
        t20 = json.load(f)

    code_prefix_20 = t20["code_id"].replace(" ", "")
    p_num_20 = t20["page_number"]
    chunks.append({
        "chunk_id": f"{code_prefix_20}-{t20['edition_year']}-TABLE-{t20['table_number']}",
        "chunk_type": "table",
        "code_id": t20["code_id"],
        "edition_year": t20["edition_year"],
        "clause_number": None,
        "table_number": t20["table_number"],
        "title": t20["title"],
        "context_path": "IS 456 > 40 Limit state of collapse: shear",
        "page_number": [p_num_20] if isinstance(p_num_20, int) else p_num_20,
        "text": render_table_20(t20),
        "cross_references": t20.get("clause_references", []),
        "citation": f"{t20['code_id']}:{t20['edition_year']} Table {t20['table_number']}",
        "verified": t20["verified"],
    })

    # 5. Process Table xu_max (1 chunk)
    with open(TABLE_XU_MAX_FILE, "r", encoding="utf-8") as f:
        txu = json.load(f)

    p_num_xu = txu["page_number"]
    chunks.append({
        "chunk_id": "IS456-2000-TABLE-XU-MAX-38.1",
        "chunk_type": "table",
        "code_id": txu["code_id"],
        "edition_year": txu["edition_year"],
        "clause_number": txu["clause_reference"],
        "table_number": None,
        "title": txu["title"],
        "context_path": "IS 456 > 38 Limit state of collapse: flexure",
        "page_number": [p_num_xu] if isinstance(p_num_xu, int) else p_num_xu,
        "text": render_xu_max_table(txu),
        "cross_references": [txu["clause_reference"]],
        "citation": "IS 456:2000 Cl. 38.1 (note: limiting depth of neutral axis)",
        "verified": txu["verified"],
    })

    # 6. Process Annex G (5 chunks)
    with open(ANNEX_G_FILE, "r", encoding="utf-8") as f:
        annex_g = json.load(f)

    p_num_g = annex_g["page_number"]
    page_list_g = [p_num_g] if isinstance(p_num_g, int) else p_num_g
    for item in annex_g["items"]:
        if item["id"] == "G-2" or "not implemented" in item.get("text", "").lower():
            continue
        chunk_id = f"IS456-2000-ANNEX-G-{item['id']}"
        citation = f"IS 456:2000 Annex G, {item['id']}"
        heading = item.get("heading")
        title = f"{item['id']} {heading}" if heading else annex_g["title"]
        text = f"{item['id']} {heading}: {item['text']}" if heading else f"{item['id']}\n{item['text']}"
        chunks.append({
            "chunk_id": chunk_id,
            "chunk_type": "clause",
            "code_id": annex_g["code_id"],
            "edition_year": annex_g["edition_year"],
            "clause_number": item["id"],
            "table_number": None,
            "title": title,
            "context_path": "IS 456 > Annex G Moments of resistance for rectangular and T-sections",
            "page_number": page_list_g,
            "text": text,
            "cross_references": [],
            "citation": citation,
            "verified": annex_g["verified"],
        })

    # 7. Process Clause 40 (5 chunks)
    with open(CL_40_FILE, "r", encoding="utf-8") as f:
        cl_40 = json.load(f)

    p_num_40 = cl_40["page_number"]
    page_list_40 = [p_num_40] if isinstance(p_num_40, int) else p_num_40
    valid_ids_40 = ["40.1", "40.2.3", "40.3", "40.4", "40.4(a)"]

    for item in cl_40["items"]:
        if item["id"] not in valid_ids_40:
            continue
        chunk_id = f"IS456-2000-CL-{item['id']}"
        citation = f"IS 456:2000 Cl. {item['id']}"

        if item["id"] == "40.2.3":
            cross_refs = ["Table 20"]
        elif item["id"] == "40.3":
            cross_refs = ["Table 19", "26.5.1.6"]
        else:
            cross_refs = []

        heading = item.get("heading")
        title = f"{item['id']} {heading}" if heading else cl_40["title"]
        text = f"{item['id']} {heading}: {item['text']}" if heading else f"{item['id']}\n{item['text']}"

        chunks.append({
            "chunk_id": chunk_id,
            "chunk_type": "clause",
            "code_id": cl_40["code_id"],
            "edition_year": cl_40["edition_year"],
            "clause_number": item["id"],
            "table_number": None,
            "title": title,
            "context_path": "IS 456 > 40 Limit state of collapse: shear",
            "page_number": page_list_40,
            "text": text,
            "cross_references": cross_refs,
            "citation": citation,
            "verified": cl_40["verified"],
        })

    # Write output JSONL
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    print(f"Successfully generated {len(chunks)} chunks to {OUTPUT_FILE}")
    return chunks


if __name__ == "__main__":
    build_chunks()
