"""
Deterministic IS 456:2000 Reinforced Concrete Design Validation (multi-rule code validator).
Runs code checks for beams, columns, slabs and isolated footings without LLM calls,
maps citations to chunk IDs, and attaches verified clause texts from data/processed/chunks.jsonl.
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
    min_bar_clear_spacing,
    max_shear_stress,
    deflection_check,
)

# NOTE: column_sizing and footing_sizing are imported lazily inside the member
# validators below. Importing them at module scope creates a cycle
# (design_validation -> footing_sizing -> beam_sizing -> design_validation).


BASE_NOTE = (
    "Passes the implemented IS 456 beam detailing checks only; "
    "not a full design check. A structural engineer must review."
)

MEMBER_NOTE = (
    "Passes the implemented IS 456 checks for this member type only; "
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
    "IS 456:2000 Cl. 40.2.3": "IS456-2000-CL-40.2.3",
    "IS 456:2000 Table 16": "IS456-2000-TABLE-16",
    "IS 456:2000 Table 19": "IS456-2000-TABLE-19",
    "IS 456:2000 Cl. 26.3.2(a)": "IS456-2000-CL-26.3.2(a)",
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

    # Also load verified Cl. 26.3.2 if available
    cl_26_3_2_path = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "is456_cl_26_3_2.json"
    if not cl_26_3_2_path.exists():
        cl_26_3_2_path = Path("data/processed/is456_cl_26_3_2.json")
    if cl_26_3_2_path.exists():
        try:
            with open(cl_26_3_2_path, "r", encoding="utf-8") as f:
                cdata = json.load(f)
                for item in cdata.get("items", []):
                    if item.get("id") == "26.3.2(a)":
                        chunks_map["IS456-2000-CL-26.3.2(a)"] = item.get("text", "")
        except Exception:
            pass

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

    # Absolute shear stress ceiling (Cl. 40.2.3 / Table 20), when a factored shear is supplied
    factored_shear_vu_kN = design.get("factored_shear_Vu_kN")
    if factored_shear_vu_kN is not None:
        tau_v = (float(factored_shear_vu_kN) * 1000.0) / (b * d)
        raw_checks.append(max_shear_stress(grade=design["fck"], tau_v_provided=round(tau_v, 4)))

    # Bar clear spacing check (IS 456 Cl. 26.3.2(a))
    max_agg = float(design.get("max_aggregate_size_mm", 20.0))
    raw_checks.append(
        min_bar_clear_spacing(
            b=b,
            cover_mm=float(cover_mm),
            stirrup_dia=stirrup_dia,
            n_bars=main_bar_count,
            bar_dia=main_bar_dia,
            max_aggregate_size_mm=max_agg,
        )
    )

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


def _finalize_member_result(member_type: str, checks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Normalizes a member's check list into a single pass/fail report.
    Every check is guaranteed to carry an explicit boolean 'passed' flag.
    """
    normalized: List[Dict[str, Any]] = []
    for c in checks:
        c_dict = dict(c)
        c_dict["passed"] = bool(c_dict.get("passed", False))
        normalized.append(c_dict)

    all_passed = all(c["passed"] for c in normalized)
    return {
        "status": "passed" if all_passed else "failed",
        "member_type": member_type,
        "checks": normalized,
        "notes": MEMBER_NOTE,
    }


def validate_column_design(design: Dict[str, Any]) -> Dict[str, Any]:
    """
    Runs the deterministic IS 456 column checks that gate CAD generation:
    slenderness (Cl. 25.1.2) and minimum eccentricity (Cl. 25.4 & Cl. 39.1).
    No LLM calls.

    Args:
        design: dict containing length_m, b_mm, D_mm and optionally effective_length_ratio.
    """
    for k in ("length_m", "b_mm", "D_mm"):
        if k not in design or design[k] is None:
            raise ValueError(f"Missing required column design parameter: '{k}'")

    from src.generation.column_sizing import (
        check_slenderness,
        check_minimum_eccentricity,
    )

    length_m = float(design["length_m"])
    b_mm = float(design["b_mm"])
    D_mm = float(design["D_mm"])
    ratio = float(design.get("effective_length_ratio", 1.0))

    slenderness = check_slenderness(length_m, b_mm, D_mm, ratio)
    slenderness["check"] = "slenderness"
    slenderness["passed"] = bool(slenderness["is_short"])

    eccentricity = check_minimum_eccentricity(length_m, b_mm, D_mm)
    eccentricity["check"] = "minimum_eccentricity"
    eccentricity["passed"] = bool(eccentricity["axial_formula_valid"])

    return _finalize_member_result("column", [slenderness, eccentricity])


def validate_slab_design(design: Dict[str, Any]) -> Dict[str, Any]:
    """
    Runs the deterministic IS 456 slab check that gates CAD generation:
    span-to-effective-depth deflection control (Cl. 23.2.1).
    No LLM calls.

    Args:
        design: dict containing span_m, d_actual_mm, b_mm, fy,
            ast_required_mm2, ast_provided_mm2 and optionally member_type.
    """
    required = ("span_m", "d_actual_mm", "b_mm", "fy", "ast_required_mm2", "ast_provided_mm2")
    for k in required:
        if k not in design or design[k] is None:
            raise ValueError(f"Missing required slab design parameter: '{k}'")

    deflection = deflection_check(
        span_m=float(design["span_m"]),
        d_actual_mm=float(design["d_actual_mm"]),
        fy=float(design["fy"]),
        ast_required_mm2=float(design["ast_required_mm2"]),
        ast_provided_mm2=float(design["ast_provided_mm2"]),
        b_mm=float(design["b_mm"]),
        member_type=str(design.get("member_type", "simply_supported")),
    )
    deflection["check"] = "deflection_control"

    return _finalize_member_result("slab", [deflection])


def validate_footing_design(design: Dict[str, Any]) -> Dict[str, Any]:
    """
    Runs the deterministic IS 456 footing checks that gate CAD generation:
    two-way punching shear (Cl. 31.6.3 & Cl. 34.2.4.1) and, when cantilever_m is
    supplied, one-way beam shear at the critical section (Cl. 34.2.4.1).
    No LLM calls.

    Args:
        design: dict containing qu_kN_m2, B_mm, L_mm, col_b_mm, col_D_mm, d_mm, fck
            and optionally cantilever_m.
    """
    required = ("qu_kN_m2", "B_mm", "L_mm", "col_b_mm", "col_D_mm", "d_mm", "fck")
    for k in required:
        if k not in design or design[k] is None:
            raise ValueError(f"Missing required footing design parameter: '{k}'")

    from src.generation.footing_sizing import (
        check_two_way_punching_shear,
        check_one_way_beam_shear,
    )

    punching = check_two_way_punching_shear(
        qu_kN_m2=float(design["qu_kN_m2"]),
        B_mm=float(design["B_mm"]),
        L_mm=float(design["L_mm"]),
        col_b_mm=float(design["col_b_mm"]),
        col_D_mm=float(design["col_D_mm"]),
        d_mm=float(design["d_mm"]),
        fck=float(design["fck"]),
    )
    punching["check"] = "two_way_punching_shear"

    checks: List[Dict[str, Any]] = [punching]

    cantilever_m = design.get("cantilever_m")
    if cantilever_m is not None:
        one_way = check_one_way_beam_shear(
            qu_kN_m2=float(design["qu_kN_m2"]),
            B_mm=float(design["B_mm"]),
            cantilever_m=float(cantilever_m),
            d_mm=float(design["d_mm"]),
            fck=float(design["fck"]),
        )
        one_way["check"] = "one_way_beam_shear"
        checks.append(one_way)

    return _finalize_member_result("footing", checks)


def validate_member(design: Dict[str, Any], member_type: str) -> Dict[str, Any]:
    """
    Dispatches a design to the deterministic IS 456 check set for its member type.
    Supported member types: "beam", "column", "slab", "footing".
    """
    mt = str(member_type).strip().lower()
    if mt == "beam":
        return validate_design(design)
    if mt == "column":
        return validate_column_design(design)
    if mt == "slab":
        return validate_slab_design(design)
    if mt == "footing":
        return validate_footing_design(design)
    raise ValueError(f"Unsupported member type: '{member_type}'")
