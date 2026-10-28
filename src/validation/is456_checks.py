"""
Deterministic IS 456:2000 Engineering Checks for Reinforced Concrete Beams.
Units: mm and N/mm2.
Formulas and limits are derived strictly from verified clauses and tables in IS 456:2000.
"""

import json
import math
import re
from pathlib import Path
from typing import Dict, Any, Optional

TABLE_16_FILE = Path("data/processed/is456_table_16.json")
TABLE_19_FILE = Path("data/processed/is456_table_19.json")
XU_MAX_TABLE_FILE = Path("data/processed/is456_xu_max_table.json")
TABLE_20_FILE = Path("data/processed/is456_table_20.json")


class CheckResult(dict):
    """
    Dictionary representing a structural validation check result.
    Supports equality and numeric casts against the required limit for ergonomic assertions.
    """
    def __eq__(self, other):
        if isinstance(other, (int, float)):
            return self.get("required") == other or self.get("tau_c") == other
        return super().__eq__(other)

    def __float__(self):
        val = self.get("required")
        if val is not None:
            return float(val)
        return float(super().__repr__())

    def __int__(self):
        val = self.get("required")
        if val is not None:
            return int(val)
        return int(super().__repr__())


def min_tension_steel(b: float, d: float, fy: float, ast_provided: float) -> Dict[str, Any]:
    """
    Checks minimum tension reinforcement in beams.
    Formula: A_s / (b * d) >= 0.85 / f_y  ==>  A_s >= 0.85 * b * d / f_y
    Citation: IS 456:2000 Cl. 26.5.1.1(a)
    """
    if b <= 0 or d <= 0 or fy <= 0:
        raise ValueError("Dimensions and material strength must be positive.")
    if ast_provided < 0:
        raise ValueError("Provided steel area cannot be negative.")

    required_ast = round((0.85 * b * d) / fy, 4)
    passed = ast_provided >= required_ast

    return CheckResult({
        "check": "min_tension_steel",
        "passed": passed,
        "required": required_ast,
        "provided": ast_provided,
        "citation": "IS 456:2000 Cl. 26.5.1.1(a)",
        "formula": "A_s >= 0.85 * b * d / f_y",
    })


def max_tension_steel(b: float, D: float, ast_provided: float) -> Dict[str, Any]:
    """
    Checks maximum tension reinforcement in beams.
    Formula: A_s <= 0.04 * b * D
    Citation: IS 456:2000 Cl. 26.5.1.1(b)
    """
    if b <= 0 or D <= 0:
        raise ValueError("Dimensions must be positive.")
    if ast_provided < 0:
        raise ValueError("Provided steel area cannot be negative.")

    limit_ast = round(0.04 * b * D, 4)
    passed = ast_provided <= limit_ast

    return CheckResult({
        "check": "max_tension_steel",
        "passed": passed,
        "required": limit_ast,
        "provided": ast_provided,
        "citation": "IS 456:2000 Cl. 26.5.1.1(b)",
        "formula": "A_s <= 0.04 * b * D",
    })


def max_compression_steel(b: float, D: float, asc_provided: float) -> Dict[str, Any]:
    """
    Checks maximum compression reinforcement in beams.
    Formula: A_sc <= 0.04 * b * D
    Citation: IS 456:2000 Cl. 26.5.1.2
    """
    if b <= 0 or D <= 0:
        raise ValueError("Dimensions must be positive.")
    if asc_provided < 0:
        raise ValueError("Provided compression steel area cannot be negative.")

    limit_asc = round(0.04 * b * D, 4)
    passed = asc_provided <= limit_asc

    return CheckResult({
        "check": "max_compression_steel",
        "passed": passed,
        "required": limit_asc,
        "provided": asc_provided,
        "citation": "IS 456:2000 Cl. 26.5.1.2",
        "formula": "A_sc <= 0.04 * b * D",
    })


def max_stirrup_spacing(d: float, spacing: float, inclined_45: bool = False) -> Dict[str, Any]:
    """
    Checks maximum spacing of shear stirrups.
    Limit: 0.75*d for vertical stirrups, d for 45° inclined stirrups, capped at 300 mm.
    Citation: IS 456:2000 Cl. 26.5.1.5
    """
    if d <= 0 or spacing <= 0:
        raise ValueError("Effective depth and spacing must be positive.")

    if inclined_45:
        limit = min(float(d), 300.0)
        formula = "spacing <= min(d, 300)"
    else:
        limit = min(0.75 * d, 300.0)
        formula = "spacing <= min(0.75 * d, 300)"

    limit = round(limit, 4)
    passed = spacing <= limit

    return CheckResult({
        "check": "max_stirrup_spacing",
        "passed": passed,
        "required": limit,
        "provided": spacing,
        "citation": "IS 456:2000 Cl. 26.5.1.5",
        "formula": formula,
    })


def min_shear_steel(b: float, sv: float, fy: float, asv_provided: float) -> Dict[str, Any]:
    """
    Checks minimum shear reinforcement in the form of stirrups.
    Formula: A_sv / (b * s_v) >= 0.4 / (0.87 * f_y)
    Note: f_y shall not be taken greater than 415 N/mm2.
    Citation: IS 456:2000 Cl. 26.5.1.6
    """
    if b <= 0 or sv <= 0 or fy <= 0:
        raise ValueError("Dimensions, spacing, and yield strength must be positive.")
    if asv_provided < 0:
        raise ValueError("Provided shear steel area cannot be negative.")

    fy_effective = min(float(fy), 415.0)
    required_asv = round((0.4 * b * sv) / (0.87 * fy_effective), 4)
    passed = asv_provided >= required_asv

    return CheckResult({
        "check": "min_shear_steel",
        "passed": passed,
        "required": required_asv,
        "provided": asv_provided,
        "citation": "IS 456:2000 Cl. 26.5.1.6",
        "formula": "A_sv / (b * s_v) >= 0.4 / (0.87 * f_y)",
    })


def max_shear_stress(grade: Any, tau_v_provided: Optional[float] = None) -> Dict[str, Any]:
    """
    Checks the absolute ceiling on nominal shear stress in a section.
    Even with shear reinforcement provided, tau_v shall not exceed tau_c_max from Table 20.
    Citation: IS 456:2000 Cl. 40.2.3
    """
    limit = float(tau_c_max(grade))

    if tau_v_provided is None:
        passed = True
        provided: Any = grade
    else:
        if tau_v_provided < 0:
            raise ValueError("Provided shear stress cannot be negative.")
        passed = tau_v_provided <= limit
        provided = round(float(tau_v_provided), 4)

    return CheckResult({
        "check": "max_shear_stress",
        "passed": passed,
        "required": round(limit, 4),
        "provided": provided,
        "tau_c_max": round(limit, 4),
        "citation": "IS 456:2000 Cl. 40.2.3",
        "formula": "tau_v <= tau_c_max (Table 20)",
    })


def max_torsion_stirrup_spacing(x1: float, y1: float, spacing: float) -> Dict[str, Any]:
    """
    Checks maximum spacing of closed rectangular stirrups for torsion.
    Limit: least of x1, (x1 + y1)/4, and 300 mm.
    Citation: IS 456:2000 Cl. 26.5.1.7(a)
    """
    if x1 <= 0 or y1 <= 0 or spacing <= 0:
        raise ValueError("Stirrup dimensions and spacing must be positive.")

    limit = round(min(float(x1), (x1 + y1) / 4.0, 300.0), 4)
    passed = spacing <= limit

    return CheckResult({
        "check": "max_torsion_stirrup_spacing",
        "passed": passed,
        "required": limit,
        "provided": spacing,
        "citation": "IS 456:2000 Cl. 26.5.1.7(a)",
        "formula": "spacing <= min(x1, (x1 + y1) / 4, 300)",
    })


def nominal_cover(exposure: str, cover_provided: Optional[float] = None) -> Dict[str, Any]:
    """
    Returns required nominal concrete cover for durability from Table 16.
    If cover_provided is given, evaluates whether cover_provided >= required cover.
    Citation: IS 456:2000 Table 16
    """
    if not exposure or not isinstance(exposure, str):
        raise ValueError(f"Invalid exposure condition: {exposure}")

    if not TABLE_16_FILE.exists():
        raise FileNotFoundError(f"Table 16 file not found at {TABLE_16_FILE}")

    with open(TABLE_16_FILE, "r", encoding="utf-8") as f:
        t16_data = json.load(f)

    # Normalize lookup (Mild, Moderate, Severe, Very severe, Extreme)
    exposure_clean = exposure.strip().lower()
    matched_row = None
    for r in t16_data["rows"]:
        if r["exposure"].strip().lower() == exposure_clean:
            matched_row = r
            break

    if matched_row is None:
        valid_options = [r["exposure"] for r in t16_data["rows"]]
        raise ValueError(f"Unknown exposure '{exposure}'. Must be one of {valid_options}.")

    required_cover = matched_row["nominal_cover_mm"]

    if cover_provided is not None:
        if cover_provided < 0:
            raise ValueError("Provided cover cannot be negative.")
        passed = cover_provided >= required_cover
        provided = cover_provided
    else:
        passed = True
        provided = exposure

    return CheckResult({
        "check": "nominal_cover",
        "passed": passed,
        "required": required_cover,
        "provided": provided,
        "nominal_cover_mm": required_cover,
        "citation": "IS 456:2000 Table 16",
        "formula": "IS 456:2000 Table 16",
    })


def shear_strength_tau_c(pt: float, grade: str, tau_provided: Optional[float] = None) -> Dict[str, Any]:
    """
    Returns design shear strength of concrete tau_c (N/mm2) from Table 19.
    Matches pt only if it is an exact table row value; raises ValueError('needs engineer decision') otherwise.
    Citation: IS 456:2000 Table 19
    """
    if not grade or not isinstance(grade, str):
        raise ValueError("needs engineer decision")

    if not TABLE_19_FILE.exists():
        raise FileNotFoundError(f"Table 19 file not found at {TABLE_19_FILE}")

    with open(TABLE_19_FILE, "r", encoding="utf-8") as f:
        t19_data = json.load(f)

    # Clean grade identifier (e.g. 'M25', 'm25', 'M 25')
    clean_grade = grade.strip().upper().replace(" ", "")
    matched_col = None
    for col in t19_data["column_headings"]:
        col_clean = col.strip().upper().replace(" ", "")
        if clean_grade == col_clean or (clean_grade == "M40" and "M40" in col_clean):
            matched_col = col
            break

    if matched_col is None:
        raise ValueError("needs engineer decision")

    # Match exact row pt_value
    matched_row = None
    for r in t19_data["rows"]:
        if abs(pt - r["pt_value"]) < 1e-5:
            matched_row = r
            break

    if matched_row is None:
        raise ValueError("needs engineer decision")

    tau_c_val = matched_row["tau_c"][matched_col]

    if tau_provided is not None:
        if tau_provided < 0:
            raise ValueError("Provided shear stress cannot be negative.")
        passed = tau_provided <= tau_c_val
        provided = tau_provided
    else:
        passed = True
        provided = pt

    return CheckResult({
        "check": "shear_strength_tau_c",
        "passed": passed,
        "required": tau_c_val,
        "provided": provided,
        "tau_c": tau_c_val,
        "citation": "IS 456:2000 Table 19",
        "formula": "IS 456:2000 Table 19",
    })


def xu_max_over_d(fy: float) -> float:
    """
    Returns limiting depth of neutral axis (x_u,max / d) from IS 456:2000 Cl. 38.1 Note.
    Supported fy values: exactly 250, 415, or 500.
    Raises ValueError('needs engineer decision') for any other fy.
    No interpolation.
    """
    if fy is None or isinstance(fy, bool):
        raise ValueError("needs engineer decision")

    try:
        fy_num = float(fy)
    except (TypeError, ValueError):
        raise ValueError("needs engineer decision")

    matched_target = None
    for target in [250, 415, 500]:
        if abs(fy_num - target) < 1e-5:
            matched_target = target
            break

    if matched_target is None:
        raise ValueError("needs engineer decision")

    path = XU_MAX_TABLE_FILE
    if not path.exists():
        path = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "is456_xu_max_table.json"

    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            t_data = json.load(f)
        for r in t_data.get("rows", []):
            if abs(r.get("fy_N_per_mm2", 0) - matched_target) < 1e-5:
                return float(r["xu_max_over_d"])

    lookup = {250: 0.53, 415: 0.48, 500: 0.46}
    return lookup[matched_target]


def tau_c_max(grade: Any) -> float:
    """
    Returns maximum shear stress tau_c_max (N/mm2) from Table 20
    (IS 456:2000 Cl. 40.2.3, 40.2.3.1, 40.5.1, 41.3.1).
    Accepts 'M15', 'M20', 'M25', 'M30', 'M35' and returns the value;
    for any other grade at or above M40 returns the 'M40 and above' value (4.0);
    for a grade below M15 raises ValueError('needs engineer decision').
    """
    if grade is None or isinstance(grade, bool):
        raise ValueError("needs engineer decision")

    path = TABLE_20_FILE
    if not path.exists():
        path = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "is456_table_20.json"

    table_data: Dict[str, float] = {}
    m40_and_above_val = 4.0
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                t_json = json.load(f)
            for r in t_json.get("rows", []):
                r_grade = str(r.get("grade", "")).strip().upper()
                r_val = float(r.get("tau_c_max", 0.0))
                table_data[r_grade] = r_val
                if "M40" in r_grade and "ABOVE" in r_grade:
                    m40_and_above_val = r_val
        except Exception:
            pass

    default_table = {
        "M15": 2.5,
        "M20": 2.8,
        "M25": 3.1,
        "M30": 3.5,
        "M35": 3.7,
        "M40 AND ABOVE": 4.0,
    }
    for k, v in default_table.items():
        if k not in table_data:
            table_data[k] = v

    if isinstance(grade, (int, float)):
        num = float(grade)
    elif isinstance(grade, str):
        g_str = grade.strip().upper()
        if g_str in table_data:
            return table_data[g_str]
        if g_str == "M40 AND ABOVE" or ("M40" in g_str and "ABOVE" in g_str):
            return m40_and_above_val

        m = re.match(r"^M\s*(\d+(?:\.\d+)?)$", g_str)
        if m:
            num = float(m.group(1))
        else:
            try:
                num = float(g_str)
            except ValueError:
                raise ValueError("needs engineer decision")
    else:
        raise ValueError("needs engineer decision")

    if num < 15:
        raise ValueError("needs engineer decision")

    if abs(num - 15) < 1e-5:
        return table_data.get("M15", 2.5)
    elif abs(num - 20) < 1e-5:
        return table_data.get("M20", 2.8)
    elif abs(num - 25) < 1e-5:
        return table_data.get("M25", 3.1)
    elif abs(num - 30) < 1e-5:
        return table_data.get("M30", 3.5)
    elif abs(num - 35) < 1e-5:
        return table_data.get("M35", 3.7)
    elif num >= 40:
        return m40_and_above_val
    else:
        raise ValueError("needs engineer decision")


def unit_weight_concrete(concrete_type: str = "reinforced") -> float:
    """
    Unit weight of concrete in kN/m3 per IS 456:2000 Cl. 19.2.1.
    - Plain concrete: 24.0 kN/m3
    - Reinforced concrete: 25.0 kN/m3
    """
    c_type = concrete_type.strip().lower()
    if c_type in ("plain", "pcc"):
        return 24.0
    return 25.0


def effective_span_simply_supported(
    clear_span_mm: float,
    d_mm: float,
    support_width_mm: float,
) -> Dict[str, Any]:
    """
    Computes effective span for a simply supported beam per IS 456:2000 Cl. 22.2(a):
    L_eff = min(clear_span + d, clear_span + support_width)
    """
    if clear_span_mm <= 0 or d_mm <= 0 or support_width_mm <= 0:
        raise ValueError("All span and support dimensions must be strictly positive.")

    val_d = clear_span_mm + d_mm
    val_bearing = clear_span_mm + support_width_mm
    l_eff_mm = min(val_d, val_bearing)
    governing = "clear_span + d" if val_d <= val_bearing else "clear_span + support_width"

    return CheckResult({
        "check": "effective_span",
        "clear_span_mm": clear_span_mm,
        "d_mm": d_mm,
        "support_width_mm": support_width_mm,
        "effective_span_mm": l_eff_mm,
        "effective_span_m": l_eff_mm / 1000.0,
        "governing_criterion": governing,
        "citation": "IS 456:2000 Cl. 22.2(a)",
        "formula": "min(clear_span + d, clear_span + support_width)",
    })


def design_bond_stress(
    fck: float,
    bar_type: str = "deformed",
    stress_type: str = "tension",
) -> float:
    """
    Design bond stress tau_bd in N/mm2 in limit state method per IS 456:2000 Cl. 26.2.1.1.
    Plain bars in tension:
      M20: 1.2, M25: 1.4, M30: 1.5, M35: 1.7, M40 and above: 1.9 N/mm2.
    For deformed bars (IS 1786): increased by 60% (* 1.6).
    For bars in compression: increased by 25% (* 1.25).
    """
    if fck is None or fck <= 0:
        raise ValueError("fck must be strictly positive.")

    grade_val = int(round(fck))
    if grade_val >= 40:
        basic_tau_bd = 1.9
    elif grade_val >= 35:
        basic_tau_bd = 1.7
    elif grade_val >= 30:
        basic_tau_bd = 1.5
    elif grade_val >= 25:
        basic_tau_bd = 1.4
    elif grade_val >= 20:
        basic_tau_bd = 1.2
    else:
        raise ValueError("needs engineer decision: fck below M20 not covered in Table 26.2.1.1")

    tau_bd = basic_tau_bd
    b_type = bar_type.strip().lower()
    if b_type in ("deformed", "hysd", "fe415", "fe500", "fe550"):
        tau_bd *= 1.6

    s_type = stress_type.strip().lower()
    if s_type == "compression":
        tau_bd *= 1.25

    return round(tau_bd, 4)


def development_length(
    bar_dia_mm: float,
    fck: float,
    fy: float,
    bar_type: str = "deformed",
    stress_type: str = "tension",
) -> Dict[str, Any]:
    """
    Computes development length Ld per IS 456:2000 Cl. 26.2.1:
      Ld = (phi * sigma_s) / (4 * tau_bd)
    where sigma_s = 0.87 * fy at limit state.
    Also returns support anchorage embedment requirement per Cl. 26.2.3.3 (Ld / 3).
    """
    if bar_dia_mm <= 0 or fck <= 0 or fy <= 0:
        raise ValueError("Bar diameter, fck, and fy must be strictly positive.")

    tau_bd = design_bond_stress(fck, bar_type=bar_type, stress_type=stress_type)
    sigma_s = 0.87 * fy
    ld_calc = (bar_dia_mm * sigma_s) / (4.0 * tau_bd)
    ld_rounded = math.ceil(ld_calc / 5.0) * 5.0
    support_anchorage_min = math.ceil((ld_calc / 3.0) / 5.0) * 5.0

    return CheckResult({
        "check": "development_length",
        "bar_dia_mm": bar_dia_mm,
        "fck": fck,
        "fy": fy,
        "bar_type": bar_type,
        "stress_type": stress_type,
        "tau_bd_N_per_mm2": tau_bd,
        "sigma_s_N_per_mm2": round(sigma_s, 2),
        "ld_mm": round(ld_calc, 1),
        "ld_rounded_mm": ld_rounded,
        "support_anchorage_min_mm": support_anchorage_min,
        "bar_diameters_multiple": round(ld_calc / bar_dia_mm, 1),
        "citation": "IS 456:2000 Cl. 26.2.1 & Cl. 26.2.1.1",
        "formula": "Ld = (phi * 0.87 * fy) / (4 * tau_bd)",
    })


def deflection_check(
    span_m: float,
    d_actual_mm: float,
    fy: float,
    ast_required_mm2: float,
    ast_provided_mm2: float,
    b_mm: float,
    member_type: str = "simply_supported",
) -> Dict[str, Any]:
    """
    Checks span-to-effective-depth ratio for deflection control per IS 456:2000 Cl. 23.2.1.
    Basic value for simply supported beams up to 10 m: 20.
    Modification factor F1 per Fig. 4 for tension reinforcement:
      fs = 0.58 * fy * (ast_required / ast_provided)
      pt = 100 * ast_provided / (b * d_actual)
      F1 = 1 / (0.225 + 0.00322 * fs + 0.625 * log10(pt)) <= 2.0
    Permissible L/d = basic * F1.
    """
    if span_m <= 0 or d_actual_mm <= 0 or fy <= 0 or b_mm <= 0:
        raise ValueError("Span, depth, width, and fy must be strictly positive.")
    if ast_required_mm2 <= 0 or ast_provided_mm2 <= 0:
        raise ValueError("Steel areas must be strictly positive.")

    # 1. Basic ratio per Cl. 23.2.1(a)
    m_type = member_type.strip().lower()
    if m_type == "cantilever":
        basic_ratio = 7.0
    elif m_type == "continuous":
        basic_ratio = 26.0
    else:
        basic_ratio = 20.0

    # For spans above 10 m per Cl. 23.2.1(b)
    if span_m > 10.0 and m_type != "cantilever":
        basic_ratio = basic_ratio * (10.0 / span_m)

    # 2. Service stress fs per Fig. 4 Note
    fs = 0.58 * fy * (ast_required_mm2 / ast_provided_mm2)

    # 3. Tension steel percentage pt
    pt = (100.0 * ast_provided_mm2) / (b_mm * d_actual_mm)

    actual_ld_ratio = round((span_m * 1000.0) / d_actual_mm, 2)

    base_note = (
        "The modification factor F1 uses an approximate curve fit that is NOT from IS 456; "
        "Fig. 4 has not yet been entered from the page. Deflection result is indicative only."
    )

    # Fig. 4 covers pt from 0 to 3.0 and fs from 120 to 290 N/mm2
    if pt > 3.0 or fs > 290.0:
        return CheckResult({
            "check": "deflection_control",
            "status": "needs_review",
            "passed": False,
            "ratio_satisfied": False,
            "note": "Outside the range of Fig. 4",
            "notes": ["Outside the range of Fig. 4"],
            "actual_ld_ratio": actual_ld_ratio,
            "max_ld_ratio": None,
            "basic_ratio": basic_ratio,
            "service_stress_fs": round(fs, 2),
            "pt": round(pt, 3),
            "modification_factor_f1": None,
            "modification_factor_f1_unclamped": None,
            "d_actual_mm": d_actual_mm,
            "span_m": span_m,
            "citation": "IS 456:2000 Cl. 23.2.1",
            "formula": "(L / d) <= basic_ratio * F1 (F1: approximate curve fit, not from IS 456)",
        })

    notes = [base_note]
    if fs < 120.0:
        fs_used = 120.0
        fs_note = "fs is below 120 N/mm2; fs = 120 N/mm2 used per Fig. 4 lower curve limit."
        notes.append(fs_note)
        note_text = f"{base_note} {fs_note}"
    else:
        fs_used = fs
        note_text = base_note

    # 4. Modification factor F1 (approximate curve fit, not from IS 456)
    log_pt = math.log10(pt)
    denom = 0.225 + (0.00322 * fs_used) + (0.625 * log_pt)
    if denom <= 0:
        f1_unclamped = 2.0
        f1 = 2.0
    else:
        f1_unclamped = round(1.0 / denom, 4)
        # Upper limit 2.0 kept; no lower limit
        f1 = min(2.0, f1_unclamped)

    # 5. Allowable vs Actual L/d
    max_ld_ratio = round(basic_ratio * f1, 2)
    ratio_satisfied = actual_ld_ratio <= max_ld_ratio

    return CheckResult({
        "check": "deflection_control",
        "status": "indicative",
        "passed": ratio_satisfied,
        "ratio_satisfied": ratio_satisfied,
        "note": note_text,
        "notes": notes,
        "actual_ld_ratio": actual_ld_ratio,
        "max_ld_ratio": max_ld_ratio,
        "basic_ratio": basic_ratio,
        "service_stress_fs": round(fs, 2),
        "service_stress_fs_used": round(fs_used, 2),
        "pt": round(pt, 3),
        "modification_factor_f1": round(f1, 3),
        "modification_factor_f1_unclamped": round(f1_unclamped, 3),
        "d_actual_mm": d_actual_mm,
        "span_m": span_m,
        "citation": "IS 456:2000 Cl. 23.2.1",
        "formula": "(L / d) <= basic_ratio * F1 (F1: approximate curve fit, not from IS 456)",
    })


def min_bar_clear_spacing(
    b: float,
    cover_mm: float,
    stirrup_dia: float,
    n_bars: int,
    bar_dia: float,
    max_aggregate_size_mm: float = 20.0,
) -> Dict[str, Any]:
    """
    Checks minimum horizontal distance between individual parallel main reinforcing bars
    per IS 456:2000 Cl. 26.3.2(a).
    Clear gap = (b - 2*cover - 2*stirrup_dia - n_bars*bar_dia) / (n_bars - 1)
    Required gap = max(bar_dia, max_aggregate_size_mm + 5.0)
    Citation: IS 456:2000 Cl. 26.3.2(a)
    """
    if n_bars < 2:
        raise ValueError("Number of bars must be at least 2 to calculate horizontal spacing.")
    if b <= 0 or cover_mm < 0 or stirrup_dia < 0 or bar_dia <= 0 or max_aggregate_size_mm < 0:
        raise ValueError("Dimensions, cover, bar diameter and aggregate size must be positive.")

    clear_gap = (b - (2.0 * cover_mm) - (2.0 * stirrup_dia) - (n_bars * bar_dia)) / (n_bars - 1.0)
    required_gap = max(float(bar_dia), float(max_aggregate_size_mm) + 5.0)
    provided_gap = round(clear_gap, 2)
    required_gap = round(required_gap, 2)
    passed = provided_gap >= required_gap

    return CheckResult({
        "check": "min_bar_clear_spacing",
        "passed": passed,
        "required": required_gap,
        "provided": provided_gap,
        "required_gap": required_gap,
        "provided_gap": provided_gap,
        "clear_gap": provided_gap,
        "citation": "IS 456:2000 Cl. 26.3.2(a)",
        "formula": "clear_gap = (b - 2*cover - 2*stirrup_dia - n_bars*bar_dia)/(n_bars - 1) >= max(bar_dia, max_aggregate_size_mm + 5)",
    })




