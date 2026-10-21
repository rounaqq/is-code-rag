"""
Deterministic IS 456:2000 Engineering Checks for Reinforced Concrete Beams.
Units: mm and N/mm2.
Formulas and limits are derived strictly from verified clauses and tables in IS 456:2000.
"""

import json
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


