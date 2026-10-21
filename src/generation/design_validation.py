"""
Deterministic IS 456:2000 Reinforced Concrete Beam Design Validation.
Runs code checks without LLM calls, maps citations to chunk IDs,
and attaches verified clause texts from data/processed/chunks.jsonl.
Does NOT import, read, print, or quote .env or any secret keys.
"""

import json
import math
from pathlib import Path
from typing import Dict, Any, Optional, List

from src.validation.is456_checks import (
    nominal_cover,
    min_tension_steel,
    max_tension_steel,
    max_compression_steel,
    max_stirrup_spacing,
    min_shear_steel,
)

BASE_NOTE = (
    "Passes the implemented IS 456 beam detailing checks only; "
    "not a full design check. A structural engineer must review."
)

CITATION_TO_CHUNK_ID = {
    "IS 456:2000 Cl. 26.5.1.1(a)": "IS456-2000-CL-26.5.1.1(a)",
    "IS 456:2000 Cl. 26.5.1.1(b)": "IS456-2000-CL-26.5.1.1(b)",
    "IS 456:2000 Cl. 26.5.1.2": "IS456-2000-CL-26.5.1.2",
    "IS 456:2000 Cl. 26.5.1.3": "IS456-2000-CL-26.5.1.3",
    "IS 456:2000 Cl. 26.5.1.4": "IS456-2000-CL-26.5.1.4",
    "IS 456:2000 Cl. 26.5.1.5": "IS456-2000-CL-26.5.1.5",
    "IS 456:2000 Cl. 26.5.1.6": "IS456-2000-CL-26.5.1.6",
    "IS 456:2000 Cl. 26.5.1.7": "IS456-2000-CL-26.5.1.7",
    "IS 456:2000 Cl. 26.5.1.7(a)": "IS456-2000-CL-26.5.1.7",
    "IS 456:2000 Cl. 26.5.1.8": "IS456-2000-CL-26.5.1.8",
    "IS 456:2000 Table 16": "IS456-2000-TABLE-16",
    "IS 456:2000 Table 19": "IS456-2000-TABLE-19",
}

_CHUNKS_CACHE: Optional[Dict[str, str]] = None


def get_chunks_map() -> Dict[str, str]:
    """
    Reads chunks from data/processed/chunks.jsonl (encoding utf-8)
    and returns a dictionary mapping chunk_id to clause text.
    """
    global _CHUNKS_CACHE
    if _CHUNKS_CACHE is not None:
        return _CHUNKS_CACHE

    chunks_path = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "chunks.jsonl"
    if not chunks_path.exists():
        chunks_path = Path("data/processed/chunks.jsonl")

    if not chunks_path.exists():
        raise FileNotFoundError(f"Chunks file not found at {chunks_path}")

    chunks_map = {}
    with open(chunks_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            cid = item.get("chunk_id")
            if cid:
                chunks_map[cid] = item.get("text", "")

    _CHUNKS_CACHE = chunks_map
    return _CHUNKS_CACHE


def validate_design(design: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates a beam reinforcement detailing design against deterministic IS 456 checks.
    No LLM calls.

    Args:
        design: dict containing:
            b, D, d, fck, fy, exposure,
            main_bar_dia_mm, main_bar_count,
            stirrup_dia_mm, stirrup_spacing_mm,
            and optionally compression_bar_dia_mm, compression_bar_count.

    Returns:
        Dict with keys:
            status: "passed" if all checks pass, else "failed"
            design: original design dict
            cover_mm: nominal cover in mm
            checks: list of check dicts (each with chunk_id, citation, clause_text)
            notes: standard IS 456 review note
    """
    # 1. Validate required fields
    required_keys = [
        "b", "D", "d", "fck", "fy", "exposure",
        "main_bar_dia_mm", "main_bar_count",
        "stirrup_dia_mm", "stirrup_spacing_mm"
    ]
    for k in required_keys:
        if k not in design or design[k] is None:
            raise ValueError(f"Missing required design parameter: '{k}'")

    b = float(design["b"])
    D = float(design["D"])
    d = float(design["d"])
    fy = float(design["fy"])
    exposure = str(design["exposure"])

    main_bar_dia = float(design["main_bar_dia_mm"])
    main_bar_count = int(design["main_bar_count"])
    stirrup_dia = float(design["stirrup_dia_mm"])
    stirrup_spacing = float(design["stirrup_spacing_mm"])

    # 1. Take cover from nominal_cover(exposure) (Table 16)
    cover_res = nominal_cover(exposure)
    cover_mm = cover_res["required"]

    # 2. Compute areas
    # Tension reinforcement area: pi * dia^2 / 4 * count
    ast_provided = (math.pi * (main_bar_dia ** 2) / 4.0) * main_bar_count
    # Stirrup area with two legs: 2 * (pi * dia^2 / 4)
    asv_provided = 2.0 * (math.pi * (stirrup_dia ** 2) / 4.0)

    # Run applicable checks
    raw_checks: List[Dict[str, Any]] = []

    # Nominal cover check
    raw_checks.append(cover_res)

    # Tension steel checks
    raw_checks.append(min_tension_steel(b=b, d=d, fy=fy, ast_provided=ast_provided))
    raw_checks.append(max_tension_steel(b=b, D=D, ast_provided=ast_provided))

    # Compression steel check (optional)
    comp_dia = design.get("compression_bar_dia_mm")
    comp_count = design.get("compression_bar_count")
    if comp_dia is not None and comp_count is not None and int(comp_count) > 0:
        asc_provided = (math.pi * (float(comp_dia) ** 2) / 4.0) * int(comp_count)
        raw_checks.append(max_compression_steel(b=b, D=D, asc_provided=asc_provided))

    # Shear stirrup checks
    raw_checks.append(max_stirrup_spacing(d=d, spacing=stirrup_spacing, inclined_45=False))
    raw_checks.append(min_shear_steel(b=b, sv=stirrup_spacing, fy=fy, asv_provided=asv_provided))

    # 3. Map each check's citation to its chunk_id and read clause text from chunks.jsonl
    chunks_map = get_chunks_map()
    enriched_checks = []
    for c in raw_checks:
        c_dict = dict(c)
        citation = c_dict.get("citation")
        if not citation:
            raise KeyError(f"Check '{c_dict.get('check')}' is missing a citation.")

        if citation not in CITATION_TO_CHUNK_ID:
            raise KeyError(f"Missing chunk_id mapping for citation: '{citation}'")

        chunk_id = CITATION_TO_CHUNK_ID[citation]
        if chunk_id not in chunks_map:
            raise KeyError(f"Clause text not found in chunks.jsonl for chunk_id: '{chunk_id}'")

        clause_text = chunks_map[chunk_id]
        c_dict["chunk_id"] = chunk_id
        c_dict["citation"] = citation
        c_dict["clause_text"] = clause_text
        c_dict["text"] = clause_text
        enriched_checks.append(c_dict)

    # 4. Determine overall status
    all_passed = all(c.get("passed", False) for c in enriched_checks)
    status = "passed" if all_passed else "failed"

    return {
        "status": status,
        "design": design,
        "cover_mm": cover_mm,
        "checks": enriched_checks,
        "notes": BASE_NOTE,
    }
