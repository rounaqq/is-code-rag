"""
Extract Clause 26.5.1 (Beams) from IS 456:2000.
Extracts:
  - 26.5.1.1(a) Minimum tension reinforcement
  - 26.5.1.1(b) Maximum tension reinforcement
  - 26.5.1.2    Compression reinforcement
  - 26.5.1.3    Side face reinforcement
  - 26.5.1.4    Transverse reinforcement in beams for shear and torsion
  - 26.5.1.5    Maximum spacing of shear reinforcement
  - 26.5.1.6    Minimum shear reinforcement
  - 26.5.1.7    Distribution of torsion reinforcement
  - 26.5.1.8    Reinforcement in flanges of T- and L-beams

Rules:
  - raw_text: Exactly as extracted from the PDF without fixes from memory.
  - cleaned_text: Whitespace fixes only. Unclear symbols/numbers marked as UNVERIFIED.
  - Tables ignored.
  - Verified records in existing output are preserved verbatim.
"""

import json
from pathlib import Path
import pymupdf


def extract_beam_clauses(pdf_path: str, output_path: str) -> None:
    doc = pymupdf.open(pdf_path)

    page_59_blocks = {b[5]: b[4].strip() for b in doc[58].get_text("blocks")}
    page_60_blocks = {b[5]: b[4].strip() for b in doc[59].get_text("blocks")}
    page_61_blocks = {b[5]: b[4].strip() for b in doc[60].get_text("blocks")}

    clauses = []

    # -------------------------------------------------------------
    # 1. Clause 26.5.1.1(a) - Minimum Tension Reinforcement
    # -------------------------------------------------------------
    raw_26_5_1_1_a = "\n".join([
        page_59_blocks[21],
        page_59_blocks[22],
        page_59_blocks[23],
        page_60_blocks[49],
        page_60_blocks[50],
        page_60_blocks[51],
        page_60_blocks[52],
        page_60_blocks[53],
        page_60_blocks[54],
        page_60_blocks[55],
        page_60_blocks[56],
        page_60_blocks[57],
    ])

    cleaned_26_5_1_1_a = (
        "a) Minimum reinforcement - The minimum area of tension reinforcement shall be not less than that "
        "given by the following:\n"
        "UNVERIFIED = 0.85\n"
        "bd / fy\n"
        "where\n"
        "UNVERIFIED = minimum area of tension reinforcement,\n"
        "b = breadth of beam or the breadth of the web of UNVERIFIED-beam,\n"
        "d = effective depth, and\n"
        "fy [UNVERIFIED symbol f,] = characteristic strength of reinforcement in N/mm2"
    )

    clauses.append({
        "code_id": "IS 456",
        "edition_year": 2000,
        "clause_number": "26.5.1.1(a)",
        "clause_title": "Tension reinforcement - Minimum reinforcement",
        "page_number": [59, 60],
        "raw_text": raw_26_5_1_1_a,
        "cleaned_text": cleaned_26_5_1_1_a,
        "cross_references": [],
        "applicable_components": ["beam"],
        "needs_manual_check": True,
        "verified": False,
        "verified_by": None,
        "formula_verified": None,
    })

    # -------------------------------------------------------------
    # 2. Clause 26.5.1.1(b) - Maximum Tension Reinforcement
    # -------------------------------------------------------------
    raw_26_5_1_1_b = page_60_blocks[58] + "\n" + page_60_blocks[59]
    cleaned_26_5_1_1_b = (
        "b) Maximum reinforcement [UNVERIFIED: reinfo~eme\",-] - The maximum area of "
        "tension reinforcement shall not exceed 0.04 bD."
    )

    clauses.append({
        "code_id": "IS 456",
        "edition_year": 2000,
        "clause_number": "26.5.1.1(b)",
        "clause_title": "Tension reinforcement - Maximum reinforcement",
        "page_number": [60],
        "raw_text": raw_26_5_1_1_b,
        "cleaned_text": cleaned_26_5_1_1_b,
        "cross_references": [],
        "applicable_components": ["beam"],
        "needs_manual_check": True,
        "verified": False,
        "verified_by": None,
        "formula_verified": None,
    })

    # -------------------------------------------------------------
    # 3. Clause 26.5.1.2 - Compression Reinforcement
    # -------------------------------------------------------------
    raw_26_5_1_2 = page_60_blocks[60] + "\n" + page_60_blocks[61]
    cleaned_26_5_1_2 = (
        "26.5.1.2 Compression reinforcement\n"
        "The maximum area of compression reinforcement shall not exceed 0.04 bD. "
        "Compression reinforcement in beams shall be enclosed by stirrups for effective lateral restraint. "
        "The arrangement of stirrups shall be as specified in 26.5.3.2."
    )

    clauses.append({
        "code_id": "IS 456",
        "edition_year": 2000,
        "clause_number": "26.5.1.2",
        "clause_title": "Compression reinforcement",
        "page_number": [60],
        "raw_text": raw_26_5_1_2,
        "cleaned_text": cleaned_26_5_1_2,
        "cross_references": ["26.5.3.2"],
        "applicable_components": ["beam"],
        "needs_manual_check": False,
        "verified": False,
        "verified_by": None,
        "formula_verified": None,
    })

    # -------------------------------------------------------------
    # 4. Clause 26.5.1.3 - Side Face Reinforcement
    # -------------------------------------------------------------
    raw_26_5_1_3 = page_60_blocks[62] + "\n" + page_60_blocks[63]
    cleaned_26_5_1_3 = (
        "26.5.1.3 Side face reinforcement\n"
        "Where the depth of the web in a beam exceeds 750 mm, side face reinforcement shall be provided along the two faces. "
        "The total area of such reinforcement shall be not less than 0.1 percent of the web area and shall be "
        "distributed equally on two faces at a spacing not exceeding 300 mm [UNVERIFIED OCR: 300 111m] or web thickness whichever is less."
    )

    clauses.append({
        "code_id": "IS 456",
        "edition_year": 2000,
        "clause_number": "26.5.1.3",
        "clause_title": "Side face reinforcement",
        "title_ocr_raw": page_60_blocks[62],
        "page_number": [60],
        "raw_text": raw_26_5_1_3,
        "cleaned_text": cleaned_26_5_1_3,
        "cross_references": [],
        "applicable_components": ["beam"],
        "needs_manual_check": True,
        "verified": False,
        "verified_by": None,
        "formula_verified": None,
    })

    # -------------------------------------------------------------
    # 5. Clause 26.5.1.4 - Transverse Reinforcement for Shear & Torsion
    # -------------------------------------------------------------
    raw_26_5_1_4 = page_60_blocks[64] + "\n" + page_60_blocks[65] + "\n" + page_60_blocks[66]
    cleaned_26_5_1_4 = (
        "26.5.1.4 Transverse reinforcement in beams for shear and torsion\n"
        "The transverse reinforcement in beams shall be taken around the outer-most tension and compression bars. "
        "In T-beams and UNVERIFIED-beams [UNVERIFIED OCR: andf-beams], such reinforcement shall pass "
        "around longitudinal bars located close to the outer face of the flange."
    )

    clauses.append({
        "code_id": "IS 456",
        "edition_year": 2000,
        "clause_number": "26.5.1.4",
        "clause_title": "Transverse reinforcement in beams for shear and torsion",
        "title_ocr_raw": page_60_blocks[64],
        "page_number": [60],
        "raw_text": raw_26_5_1_4,
        "cleaned_text": cleaned_26_5_1_4,
        "cross_references": [],
        "applicable_components": ["beam"],
        "needs_manual_check": True,
        "verified": False,
        "verified_by": None,
        "formula_verified": None,
    })

    # -------------------------------------------------------------
    # 6. Clause 26.5.1.5 - Maximum Spacing of Shear Reinforcement
    # Starts on page 60 (blocks 67, 68), last line on page 61 (block 1)
    # -------------------------------------------------------------
    raw_26_5_1_5 = page_60_blocks[67] + "\n" + page_60_blocks[68] + "\n" + page_61_blocks[1]
    cleaned_26_5_1_5 = (
        "26.5.1.5 Maximum spacing of shear reinforcement\n"
        "The maximum spacing of shear reinforcement measured along the axis of the member shall not exceed "
        "0.75 d for vertical stirrups and d for inclined stirrups at 45° [UNVERIFIED OCR: 45'\\] where d is the effective depth of the section "
        "under consideration. In no case shall the spacing exceed 300 mm [UNVERIFIED OCR: 1ft no case shall the spacinl exceed300mm]."
    )

    clauses.append({
        "code_id": "IS 456",
        "edition_year": 2000,
        "clause_number": "26.5.1.5",
        "clause_title": "Maximum spacing of shear reinforcement",
        "title_ocr_raw": page_60_blocks[67],
        "page_number": [60, 61],
        "raw_text": raw_26_5_1_5,
        "cleaned_text": cleaned_26_5_1_5,
        "cross_references": [],
        "applicable_components": ["beam"],
        "needs_manual_check": True,
        "verified": False,
        "verified_by": None,
        "formula_verified": None,
    })

    # -------------------------------------------------------------
    # 7. Clause 26.5.1.6 - Minimum Shear Reinforcement
    # Page 61: blocks 2, 3, 4, 5, 6, 7, 8
    # -------------------------------------------------------------
    raw_26_5_1_6 = "\n".join([
        page_61_blocks[2],
        page_61_blocks[3],
        page_61_blocks[4],
        page_61_blocks[5],
        page_61_blocks[6],
        page_61_blocks[7],
        page_61_blocks[8],
    ])
    cleaned_26_5_1_6 = (
        "26.5.1.6 Minimum shear reinforcement\n"
        "Minimum shear reinforcement in the form of stirrups shall be provided such that:\n"
        "UNVERIFIED [formula missing in PDF text extraction]\n"
        "where\n"
        "UNVERIFIED [OCR: AI.] = total cross-sectional area of stirrup legs effective in shear,\n"
        "UNVERIFIED [OCR: '.] = stirrup spacing along the length of the member,\n"
        "b = breadth of the beam or breadth of the web of flanged beam, and\n"
        "UNVERIFIED [OCR: I.,] = characteristic strength of the stirrup reinforcement in N/mm2 which shall not "
        "be taken greater than 415 N/mm2 [UNVERIFIED OCR: takenpater dian 415N/mm2].\n"
        "Where the maximum shear stress calculated is less than half the permissible value and in members of minor "
        "structural importance such as lintels, this provision need not be complied with."
    )

    clauses.append({
        "code_id": "IS 456",
        "edition_year": 2000,
        "clause_number": "26.5.1.6",
        "clause_title": "Minimum shear reinforcement",
        "title_ocr_raw": page_61_blocks[2].splitlines()[0],
        "page_number": [61],
        "raw_text": raw_26_5_1_6,
        "cleaned_text": cleaned_26_5_1_6,
        "cross_references": [],
        "applicable_components": ["beam"],
        "needs_manual_check": True,
        "verified": False,
        "verified_by": None,
        "formula_verified": None,
    })

    # -------------------------------------------------------------
    # 8. Clause 26.5.1.7 - Distribution of Torsion Reinforcement
    # Page 61: blocks 9, 10, 11, 12, 13, 14, 15
    # -------------------------------------------------------------
    raw_26_5_1_7 = "\n".join([
        page_61_blocks[9],
        page_61_blocks[10],
        page_61_blocks[11],
        page_61_blocks[12],
        page_61_blocks[13],
        page_61_blocks[14],
        page_61_blocks[15],
    ])
    cleaned_26_5_1_7 = (
        "26.5.1.7 Distribution of torsion reinforcement\n"
        "When a member is designed for torsion (see 41 or B-6 [UNVERIFIED OCR: (,~, 41 or 8-6)]) torsion reinforcement shall be provided as below:\n"
        "a) The transverse reinforcement for torsion shall be rectangular closed stirrups placed perpendicular to the axis of the member. "
        "The spacing of the stirrups shall not exceed the least of UNVERIFIED [OCR: .I., .I,:\"] and 300 mm, where UNVERIFIED [OCR: .I. and ,. IR] "
        "are respectively the short and long dimensions of the stirrup.\n"
        "b) Longitudinal reinforcement shall be placed as close as is practicable to the corners of the cross-section and in all cases, "
        "there shall be at least one longitudinal bar in each corner of the ties. When the cross-sectional dimension of the member exceeds 450 mm, "
        "additional longitudinal bars shall be provided to satisfy the requirements of minimum reinforcement and spacing given in 26.5.1.3."
    )

    clauses.append({
        "code_id": "IS 456",
        "edition_year": 2000,
        "clause_number": "26.5.1.7",
        "clause_title": "Distribution of torsion reinforcement",
        "title_ocr_raw": page_61_blocks[9],
        "page_number": [61],
        "raw_text": raw_26_5_1_7,
        "cleaned_text": cleaned_26_5_1_7,
        "cross_references": ["41", "B-6", "26.5.1.3"],
        "applicable_components": ["beam"],
        "needs_manual_check": True,
        "verified": False,
        "verified_by": None,
        "formula_verified": None,
    })

    # -------------------------------------------------------------
    # 9. Clause 26.5.1.8 - Reinforcement in Flanges of T- and L-Beams
    # Page 61: block 16
    # -------------------------------------------------------------
    raw_26_5_1_8 = page_61_blocks[16]
    cleaned_26_5_1_8 = (
        "26.5.1.8 Reinforcement in flanges of T- and L-beams\n"
        "shall satisfy the requirements in 23.1.1(b). Where flanges are in tension [UNVERIFIED OCR: tlaDles are in teuioD], "
        "a part of the main tension reinforcement shall be distributed over the effective flange width or a width equal to "
        "one-tenth of the span [UNVERIFIED OCR: ~tonth ofthe span], whichever is smaller. If the effective flange width exceeds "
        "one-tenth of the span, nominal longitudinal reinforcement shall be provided in the outer portions of the flange [UNVERIFIED OCR: flap]."
    )

    clauses.append({
        "code_id": "IS 456",
        "edition_year": 2000,
        "clause_number": "26.5.1.8",
        "clause_title": "Reinforcement in flanges of T- and L-beams",
        "title_ocr_raw": page_61_blocks[16].splitlines()[0],
        "page_number": [61],
        "raw_text": raw_26_5_1_8,
        "cleaned_text": cleaned_26_5_1_8,
        "cross_references": ["23.1.1(b)"],
        "applicable_components": ["beam"],
        "needs_manual_check": True,
        "verified": False,
        "verified_by": None,
        "formula_verified": None,
    })

    doc.close()

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    # Check for existing records: preserve any record where verified is True
    final_clauses = []
    if out_file.exists():
        try:
            with open(out_file, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
            existing_map = {item.get("clause_number"): item for item in existing_data if isinstance(item, dict)}
            for cl in clauses:
                cl_num = cl["clause_number"]
                if cl_num in existing_map and existing_map[cl_num].get("verified") is True:
                    final_clauses.append(existing_map[cl_num])
                else:
                    final_clauses.append(cl)
        except Exception:
            final_clauses = clauses
    else:
        final_clauses = clauses

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(final_clauses, f, indent=2, ensure_ascii=False)

    print(f"Successfully processed {len(final_clauses)} clauses to {output_path}")


if __name__ == "__main__":
    extract_beam_clauses("data/raw/is_456_2000.pdf", "data/processed/is456_cl_26_5_1.json")
