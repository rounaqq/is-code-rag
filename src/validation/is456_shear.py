"""
Deterministic IS 456:2000 Shear Design for Rectangular RC Beams (Vertical Stirrups Only).
Follows IS 456:2000 Clause 40 (Cl. 40.1, 40.2.3, 40.3, 40.4, 40.4(a)),
Clause 26.5.1.5 (maximum stirrup spacing), Clause 26.5.1.6 (minimum shear reinforcement),
Table 19 (concrete design shear strength tau_c), and Table 20 (maximum shear stress tau_c_max).

Units: N, mm, N/mm2. No LLM. No formula or value from memory.
Does NOT import, read, print, or quote .env or any secret keys.
"""

import json
import math
from pathlib import Path
from typing import Dict, Any, Optional

from src.validation.is456_checks import tau_c_max

TABLE_19_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "is456_table_19.json"
if not TABLE_19_FILE.exists():
    TABLE_19_FILE = Path("data/processed/is456_table_19.json")

ASSUMPTION_NOTE_ROW_RULE = (
    "ASSUMPTION: Using the Table 19 row at or below pt (the first row if pt is below 0.15, "
    "the last row if pt is 3.00 or more), never a higher row. This is not from the IS 456 standard; "
    "an engineer must confirm it."
)
NOTE_AST_TENSION_CONTINUATION = (
    "ast_provided must be the tension steel that continues at least d beyond the section "
    "(IS 456 Table 19 note)."
)
NOTE_VU_CRITICAL_SECTION = (
    "vu is the design shear force at the critical section."
)
NOTE_PRACTICAL_ROUNDING = (
    "suggested_spacing_mm is rounded DOWN to a multiple of 5 mm (practical construction rounding, "
    "not from IS 456; never rounded up above calculated value)."
)


def tau_c_lookup(pt: float, fck: float) -> float:
    """
    Looks up design shear strength of concrete tau_c (N/mm2) from Table 19.

    Grade mapping from fck:
      - 15 -> 'M15'
      - 20 -> 'M20'
      - 25 -> 'M25'
      - 30 -> 'M30'
      - 35 -> 'M35'
      - fck >= 40 -> 'M40 and above'
      - any other fck raises ValueError('needs engineer decision')

    ASSUMPTION:
      Use the Table 19 row at or below pt (the first row if pt is below 0.15,
      the last row if pt is 3.00 or more), never a higher row.
      This is not from the standard; an engineer must confirm it.

    Rejects zero or negative inputs with ValueError.
    """
    if pt is None or fck is None:
        raise ValueError("Inputs cannot be None.")
    if isinstance(pt, bool) or isinstance(fck, bool):
        raise ValueError("Boolean inputs not allowed.")

    pt_val = float(pt)
    fck_val = float(fck)

    if pt_val <= 0 or fck_val <= 0:
        raise ValueError("pt and fck must be strictly positive.")

    # Grade column determination
    if fck_val in (15.0, 15):
        grade_col = "M15"
    elif fck_val in (20.0, 20):
        grade_col = "M20"
    elif fck_val in (25.0, 25):
        grade_col = "M25"
    elif fck_val in (30.0, 30):
        grade_col = "M30"
    elif fck_val in (35.0, 35):
        grade_col = "M35"
    elif fck_val >= 40.0:
        grade_col = "M40 and above"
    else:
        raise ValueError("needs engineer decision")

    if not TABLE_19_FILE.exists():
        raise FileNotFoundError(f"Table 19 file not found at {TABLE_19_FILE}")

    with open(TABLE_19_FILE, "r", encoding="utf-8") as f:
        t19_data = json.load(f)

    rows = t19_data["rows"]
    if pt_val < 0.15:
        chosen_row = rows[0]
    elif pt_val >= 3.0:
        chosen_row = rows[-1]
    else:
        eligible = [r for r in rows if r["pt_value"] <= pt_val]
        chosen_row = eligible[-1]

    return float(chosen_row["tau_c"][grade_col])


def shear_design(
    b: float,
    d: float,
    fck: float,
    fy_stirrup: float,
    vu: float,
    ast_provided: float,
    stirrup_dia: float,
    legs: int = 2,
) -> Dict[str, Any]:
    """
    Performs deterministic shear design for a rectangular RC beam with vertical stirrups.
    Follows IS 456:2000 Clause 40 (40.1, 40.2.3, 40.3, 40.4, 40.4(a)),
    Clause 26.5.1.5, Clause 26.5.1.6, Table 19, and Table 20.

    Args:
        b: Beam width in mm.
        d: Effective depth in mm.
        fck: Characteristic compressive cube strength of concrete in N/mm2.
        fy_stirrup: Characteristic strength of stirrup reinforcement in N/mm2.
        vu: Factored shear force at critical section in N.
        ast_provided: Longitudinal tension steel area continuing at least d beyond section in mm2.
        stirrup_dia: Diameter of shear stirrup bar in mm.
        legs: Number of vertical legs of stirrups (default = 2).

    Returns:
        dict with status, tau_v, tau_c, tau_c_max, pt, vus (when computed), asv,
        sv_calc, sv_min_steel, sv_cap, spacing_mm, suggested_spacing_mm, citations, notes.

    Rejects zero or negative inputs with ValueError.
    """
    # 1. Input Validation
    args = [b, d, fck, fy_stirrup, vu, ast_provided, stirrup_dia, legs]
    if any(a is None for a in args):
        raise ValueError("Inputs cannot be None.")
    if any(isinstance(a, bool) for a in args):
        raise ValueError("Boolean inputs not allowed.")

    b_val = float(b)
    d_val = float(d)
    fck_val = float(fck)
    fy_stirrup_val = float(fy_stirrup)
    vu_val = float(vu)
    ast_val = float(ast_provided)
    stirrup_dia_val = float(stirrup_dia)
    legs_val = int(legs)

    if (
        b_val <= 0
        or d_val <= 0
        or fck_val <= 0
        or fy_stirrup_val <= 0
        or vu_val <= 0
        or ast_val <= 0
        or stirrup_dia_val <= 0
        or legs_val <= 0
    ):
        raise ValueError("All inputs must be strictly positive.")

    # 2. Effective yield strength for shear reinforcement (Cl. 40.4(a): fy not greater than 415 N/mm2)
    fy_eff = min(fy_stirrup_val, 415.0)

    # 3. Nominal shear stress (Cl. 40.1)
    tau_v = vu_val / (b_val * d_val)

    # Determine grade string for Table 20 lookup
    if fck_val in (15.0, 15):
        grade_str = "M15"
    elif fck_val in (20.0, 20):
        grade_str = "M20"
    elif fck_val in (25.0, 25):
        grade_str = "M25"
    elif fck_val in (30.0, 30):
        grade_str = "M30"
    elif fck_val in (35.0, 35):
        grade_str = "M35"
    elif fck_val >= 40.0:
        grade_str = "M40 and above"
    else:
        raise ValueError("needs engineer decision")

    tau_c_max_val = float(tau_c_max(grade_str))

    # 4. Tension steel percentage and concrete shear strength (Table 19)
    pt = (100.0 * ast_val) / (b_val * d_val)
    tau_c = tau_c_lookup(pt, fck_val)

    # 5. Stirrup cross-sectional area
    asv = legs_val * math.pi * (stirrup_dia_val ** 2) / 4.0

    # 6. Minimum shear steel spacing (Cl. 26.5.1.6) & maximum spacing cap (Cl. 26.5.1.5)
    sv_min_steel = (0.87 * fy_eff * asv) / (0.4 * b_val)
    sv_cap = min(0.75 * d_val, 300.0)

    notes = [
        ASSUMPTION_NOTE_ROW_RULE,
        NOTE_AST_TENSION_CONTINUATION,
        NOTE_VU_CRITICAL_SECTION,
        NOTE_PRACTICAL_ROUNDING,
    ]

    # 7. Check if section is too small (Cl. 40.2.3: tau_v shall under no circumstances exceed tau_c_max)
    if tau_v > tau_c_max_val:
        notes.append(
            f"Under no circumstances, even with shear reinforcement, shall tau_v ({tau_v:.4f} N/mm2) "
            f"exceed tau_c_max ({tau_c_max_val:.4f} N/mm2) given in Table 20 (IS 456 Cl. 40.2.3). "
            f"The cross-section dimensions (b and/or d) must be increased."
        )
        return {
            "status": "section_too_small",
            "tau_v": tau_v,
            "tau_c": tau_c,
            "tau_c_max": tau_c_max_val,
            "pt": pt,
            "vus": None,
            "asv": asv,
            "sv_calc": None,
            "sv_min_steel": sv_min_steel,
            "sv_cap": sv_cap,
            "spacing_mm": None,
            "suggested_spacing_mm": None,
            "citations": [
                "IS 456:2000 Cl. 40.1",
                "IS 456:2000 Cl. 40.2.3",
                "IS 456:2000 Table 20",
            ],
            "notes": notes,
        }

    # 8. Shear Design Calculation
    if tau_v <= tau_c:
        # Cl. 40.3: when tau_v is less than tau_c, provide minimum shear reinforcement per 26.5.1.6
        status = "minimum_shear_steel"
        vus = None
        sv_calc = None
        spacing = min(sv_min_steel, sv_cap)
        citations = [
            "IS 456:2000 Cl. 40.1",
            "IS 456:2000 Cl. 40.3",
            "IS 456:2000 Cl. 26.5.1.5",
            "IS 456:2000 Cl. 26.5.1.6",
            "IS 456:2000 Table 19",
            "IS 456:2000 Table 20",
        ]
    else:
        # Cl. 40.4 & 40.4(a): when tau_v exceeds tau_c, provide shear reinforcement for Vu - tau_c*b*d
        vus = vu_val - (tau_c * b_val * d_val)
        sv_calc = (0.87 * fy_eff * asv * d_val) / vus
        spacing = min(sv_calc, sv_min_steel, sv_cap)
        status = "stirrups_designed"
        citations = [
            "IS 456:2000 Cl. 40.1",
            "IS 456:2000 Cl. 40.4",
            "IS 456:2000 Cl. 40.4(a)",
            "IS 456:2000 Cl. 26.5.1.5",
            "IS 456:2000 Cl. 26.5.1.6",
            "IS 456:2000 Table 19",
            "IS 456:2000 Table 20",
        ]

    # 9. Suggested spacing (practical rounding down to multiple of 5 mm)
    # Never round up and never raise spacing above calculated value
    suggested_spacing_mm = math.floor(spacing / 5.0) * 5.0

    # If calculated spacing is below 100 mm, set status "needs_review"
    if spacing < 100.0:
        status = "needs_review"
        notes.append(
            f"Calculated spacing ({spacing:.2f} mm) is below 100 mm. Very close stirrups need an "
            f"engineer's decision (larger stirrups, closer bars or a larger section)."
        )

    return {
        "status": status,
        "tau_v": tau_v,
        "tau_c": tau_c,
        "tau_c_max": tau_c_max_val,
        "pt": pt,
        "vus": vus,
        "asv": asv,
        "sv_calc": sv_calc,
        "sv_min_steel": sv_min_steel,
        "sv_cap": sv_cap,
        "spacing_mm": spacing,
        "suggested_spacing_mm": suggested_spacing_mm,
        "citations": citations,
        "notes": notes,
    }
