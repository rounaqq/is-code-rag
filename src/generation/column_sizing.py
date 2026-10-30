"""
Deterministic Structural Column Sizing Engine for IS 456:2000.
Computes short axially loaded rectangular and square RC columns with minimum eccentricity.
Covers:
  - Clause 39.3: Axial load capacity Pu = 0.4*fck*Ac + 0.67*fy*Asc
  - Clause 25.4: Minimum eccentricity emin = max(L/500 + D/30, 20mm) <= 0.05D
  - Clause 25.1.2: Slenderness ratio check Lex/D < 12 and Ley/b < 12 (Short column)
  - Clause 26.5.3.1: Longitudinal reinforcement (0.8% <= Asc/Ag <= 4.0%, min 4 bars, min dia 12mm)
  - Clause 26.5.3.2: Lateral ties diameter (>= phi_max/4 and >= 6mm) & pitch (<= min(b, 16*phi_min, 300mm))
  - Clause 26.4.2 & Table 16: Nominal cover for columns (40mm standard)
Zero LLM generation. 100% deterministic pure Python math.
"""

import math
from typing import Dict, Any, List, Optional, Tuple

COLUMN_REBAR_DIAMETERS = [12, 16, 20, 25, 32]
STANDARD_TIE_DIAMETERS = [8, 10]


def check_slenderness(
    length_m: float,
    b_mm: float,
    D_mm: float,
    effective_length_ratio: float = 1.0,
) -> Dict[str, Any]:
    """
    Checks if compression member is 'short' per IS 456 Cl. 25.1.2.
    Slenderness ratio Lex/D < 12 and Ley/b < 12.
    """
    L_eff_mm = effective_length_ratio * length_m * 1000.0
    lambda_D = round(L_eff_mm / D_mm, 2)
    lambda_b = round(L_eff_mm / b_mm, 2)
    is_short = (lambda_D < 12.0) and (lambda_b < 12.0)

    return {
        "is_short": is_short,
        "effective_length_mm": L_eff_mm,
        "lambda_D": lambda_D,
        "lambda_b": lambda_b,
        "slenderness_limit": 12.0,
        "citation": "IS 456:2000 Cl. 25.1.2",
    }


def check_minimum_eccentricity(
    length_m: float,
    b_mm: float,
    D_mm: float,
) -> Dict[str, Any]:
    """
    Checks minimum eccentricity per IS 456 Cl. 25.4 and Cl. 39.1.
    emin = max(L/500 + D/30, 20 mm) must not exceed 0.05 * D (and 0.05 * b).
    """
    L_mm = length_m * 1000.0
    emin_D = max(L_mm / 500.0 + D_mm / 30.0, 20.0)
    emin_b = max(L_mm / 500.0 + b_mm / 30.0, 20.0)

    limit_D = 0.05 * D_mm
    limit_b = 0.05 * b_mm

    valid_D = emin_D <= limit_D
    valid_b = emin_b <= limit_b
    is_pure_axial = valid_D and valid_b

    return {
        "emin_D_mm": round(emin_D, 2),
        "emin_b_mm": round(emin_b, 2),
        "limit_D_mm": round(limit_D, 2),
        "limit_b_mm": round(limit_b, 2),
        "axial_formula_valid": is_pure_axial,
        "citation": "IS 456:2000 Cl. 25.4 & Cl. 39.1",
    }


def calculate_required_steel(
    Pu_kN: float,
    b_mm: float,
    D_mm: float,
    fck: float,
    fy: float,
) -> Dict[str, Any]:
    """
    Solves for required longitudinal steel Asc per IS 456 Cl. 39.3:
      Pu = 0.4 * fck * (Ag - Asc) + 0.67 * fy * Asc
      Asc = (Pu - 0.4 * fck * Ag) / (0.67 * fy - 0.4 * fck)
    Enforces minimum 0.8% Ag and maximum 4.0% Ag (Cl. 26.5.3.1).
    """
    Ag = b_mm * D_mm
    Pu_N = Pu_kN * 1000.0

    concrete_capacity_alone_N = 0.4 * fck * Ag

    denominator = 0.67 * fy - 0.4 * fck
    if denominator <= 0:
        raise ValueError(f"Invalid material grades fck={fck}, fy={fy}")

    numerator = Pu_N - concrete_capacity_alone_N
    raw_Asc_req = numerator / denominator

    Asc_min = 0.008 * Ag  # 0.8% of Ag per Cl. 26.5.3.1(a)
    Asc_max = 0.040 * Ag  # 4.0% of Ag per Cl. 26.5.3.1(a) practical lap limit

    governing_Asc = max(raw_Asc_req, Asc_min)

    exceeds_max = governing_Asc > Asc_max

    return {
        "Ag_mm2": round(Ag, 1),
        "raw_Asc_req_mm2": round(raw_Asc_req, 1),
        "Asc_min_mm2": round(Asc_min, 1),
        "Asc_max_mm2": round(Asc_max, 1),
        "governing_Asc_req_mm2": round(governing_Asc, 1),
        "pt_req_pct": round((governing_Asc / Ag) * 100.0, 2),
        "exceeds_max_steel": exceeds_max,
        "concrete_alone_capacity_kN": round(concrete_capacity_alone_N / 1000.0, 1),
        "citation": "IS 456:2000 Cl. 39.3 & Cl. 26.5.3.1",
    }


def select_column_rebar(
    Asc_req_mm2: float,
    b_mm: float,
    D_mm: float,
    cover_mm: float = 40.0,
    tie_dia_mm: float = 8.0,
) -> Optional[Dict[str, Any]]:
    """
    Selects valid discrete symmetrical longitudinal bar arrangements:
      - 4-bar: 4 corners (square or rectangular)
      - 6-bar: 4 corners + 2 along longer face D
      - 8-bar: 4 corners + 2 along face b + 2 along face D
    Validates:
      1. Asc_provided >= Asc_req_mm2
      2. Steel % between 0.8% and 4.0%
      3. Minimum bar dia >= 12 mm (Cl. 26.5.3.1(d))
      4. Spacing along periphery <= 300 mm (Cl. 26.5.3.1(g))
      5. Clear space between adjacent bars >= max(phi, 25 mm) for concrete pouring
    """
    Ag = b_mm * D_mm
    Asc_min = 0.008 * Ag
    Asc_max = 0.040 * Ag

    candidates: List[Dict[str, Any]] = []

    # Bar counts to evaluate
    bar_counts = [4, 6, 8]

    for dia in COLUMN_REBAR_DIAMETERS:
        bar_area = (math.pi / 4.0) * (dia ** 2)

        for count in bar_counts:
            total_area = count * bar_area

            if total_area < Asc_req_mm2 or total_area < Asc_min or total_area > Asc_max:
                continue

            # Check periphery spacing
            # Core dimensions inside ties
            core_b = b_mm - 2 * cover_mm - 2 * tie_dia_mm - dia
            core_D = D_mm - 2 * cover_mm - 2 * tie_dia_mm - dia

            if core_b <= 0 or core_D <= 0:
                continue

            # Spacing between bars along sides
            if count == 4:
                # 1 bar in each corner
                spacing_x = core_b
                spacing_y = core_D
            elif count == 6:
                # 4 corners + 2 on face D
                spacing_x = core_b
                spacing_y = core_D / 2.0
            else:  # count == 8
                # 4 corners + 2 on b + 2 on D
                spacing_x = core_b / 2.0
                spacing_y = core_D / 2.0

            max_spacing = max(spacing_x, spacing_y)
            min_spacing = min(spacing_x, spacing_y)

            # Periphery spacing limit <= 300 mm
            if max_spacing > 300.0:
                continue

            # Clear spacing between bar faces must be >= max(dia, 25 mm)
            clear_min = min_spacing - dia
            if clear_min < max(dia, 25.0):
                continue

            candidates.append({
                "bar_count": count,
                "bar_diameter_mm": dia,
                "area_provided_mm2": round(total_area, 1),
                "callout": f"{count}-T{dia}",
                "pt_provided_pct": round((total_area / Ag) * 100.0, 2),
                "max_spacing_mm": round(max_spacing, 1),
                "clear_spacing_mm": round(clear_min, 1),
            })

    if not candidates:
        return None

    # Pick candidate with smallest area exceeding Asc_req
    candidates.sort(key=lambda c: (c["area_provided_mm2"], c["bar_diameter_mm"]))
    return candidates[0]


def design_lateral_ties(
    main_bar_dia_mm: float,
    b_mm: float,
    D_mm: float,
) -> Dict[str, Any]:
    """
    Designs lateral ties per IS 456 Cl. 26.5.3.2(c):
      - Diameter: >= max(main_bar_dia / 4, 6.0 mm). Standard is 8 mm.
      - Pitch: <= min(least lateral dimension, 16 * main_bar_dia, 300 mm).
      - Rounded down to nearest 10 mm.
    """
    dia_req = max(main_bar_dia_mm / 4.0, 6.0)
    tie_dia = 8.0 if dia_req <= 8.0 else 10.0

    least_dim = min(b_mm, D_mm)
    pitch_limit = min(least_dim, 16.0 * main_bar_dia_mm, 300.0)

    # Round down to multiple of 10 mm
    pitch = math.floor(pitch_limit / 10.0) * 10.0
    pitch = max(pitch, 100.0)  # practical construction floor

    return {
        "tie_diameter_mm": int(tie_dia),
        "tie_pitch_mm": int(pitch),
        "callout": f"T{int(tie_dia)} @ {int(pitch)} c/c",
        "governing_pitch_limit_mm": round(pitch_limit, 1),
        "citation": "IS 456:2000 Cl. 26.5.3.2(c)",
    }


def size_column_from_load(
    axial_load_kN: float,
    length_m: float = 3.0,
    b_mm: Optional[float] = None,
    D_mm: Optional[float] = None,
    fck: float = 25.0,
    fy: float = 500.0,
    exposure: str = "Moderate",
    effective_length_ratio: float = 1.0,
) -> Dict[str, Any]:
    """
    Full end-to-end IS 456 deterministic column design:
      1. Factors axial load Pu = 1.5 * P
      2. Determines or auto-sizes cross-section dimensions (b x D)
      3. Verifies slenderness (short column condition Lex/D < 12)
      4. Verifies minimum eccentricity (emin <= 0.05D)
      5. Solves for longitudinal steel Asc (0.8% <= Asc/Ag <= 4.0%)
      6. Selects discrete rebar arrangement (4-T20, 6-T16, etc.)
      7. Designs lateral ties (e.g. T8 @ 300 c/c)
      8. Checks nominal cover (40 mm per Table 16)
    """
    Pu_kN = round(axial_load_kN * 1.5, 2)
    cover_mm = 40.0  # Table 16 standard for columns

    # Auto-size square section if dimensions not specified
    if b_mm is None or D_mm is None:
        # Effective stress approx: 0.4*fck + 0.0067*fy
        approx_stress = 0.4 * fck + 0.0067 * fy
        Ag_trial = (Pu_kN * 1000.0) / approx_stress
        dim_trial = math.sqrt(Ag_trial)
        # Cl. 39.1 requires emin <= 0.05*D. Since emin >= 20mm, 0.05*D >= 20mm requires D >= 400mm.
        # Round up to multiple of 50 mm, minimum 400 mm for axial formula validity.
        dim = max(math.ceil(dim_trial / 50.0) * 50.0, 400.0)
        b_mm = dim
        D_mm = dim
    else:
        b_mm = float(b_mm)
        D_mm = float(D_mm)

    status = "success"
    reason = None

    # 1. Slenderness check
    slenderness = check_slenderness(length_m, b_mm, D_mm, effective_length_ratio)
    if not slenderness["is_short"]:
        status = "needs_review"
        reason = f"Column is slender (lambda_D={slenderness['lambda_D']}, lambda_b={slenderness['lambda_b']} >= 12). Requires second-order moment design (Cl. 39.7). Enlarge section."

    # 2. Minimum eccentricity check
    eccentricity = check_minimum_eccentricity(length_m, b_mm, D_mm)
    if not eccentricity["axial_formula_valid"] and status == "success":
        status = "needs_review"
        reason = f"Minimum eccentricity exceeds 0.05*D (emin_D={eccentricity['emin_D_mm']} > {eccentricity['limit_D_mm']} or emin_b={eccentricity['emin_b_mm']} > {eccentricity['limit_b_mm']}). Pure axial formula Cl. 39.3 requires emin <= 0.05*dimension. Increase section width b to >= 400 mm, or verify under combined bending (Cl. 39.5)."

    # 3. Required steel calculation
    steel_calc = calculate_required_steel(Pu_kN, b_mm, D_mm, fck, fy)
    if steel_calc["exceeds_max_steel"]:
        return {
            "status": "needs_review",
            "reason": f"Required steel ({steel_calc['pt_req_pct']}%) exceeds maximum code limit of 4.0% Ag. Enlarge column cross-section.",
            "section_dimensions": f"{int(b_mm)}x{int(D_mm)} mm",
            "steel_calculation": steel_calc,
            "slenderness": slenderness,
            "eccentricity": eccentricity,
        }

    # 4. Rebar selection
    rebar = select_column_rebar(steel_calc["governing_Asc_req_mm2"], b_mm, D_mm, cover_mm)
    if not rebar:
        return {
            "status": "needs_review",
            "reason": "Could not find a valid rebar arrangement satisfying clear spacing and periphery limits. Enlarge cross-section.",
            "section_dimensions": f"{int(b_mm)}x{int(D_mm)} mm",
            "steel_calculation": steel_calc,
            "slenderness": slenderness,
            "eccentricity": eccentricity,
        }

    # 5. Lateral ties design
    ties = design_lateral_ties(rebar["bar_diameter_mm"], b_mm, D_mm)

    # 6. Actual capacity check with provided steel
    Asc_provided = rebar["area_provided_mm2"]
    Ag = b_mm * D_mm
    Ac = Ag - Asc_provided
    Pu_capacity_kN = round((0.4 * fck * Ac + 0.67 * fy * Asc_provided) / 1000.0, 1)

    design_dict = {
        "member_type": "column",
        "section_dimensions": f"{int(b_mm)}x{int(D_mm)} mm",
        "width_mm": int(b_mm),
        "depth_mm": int(D_mm),
        "length_m": length_m,
        "fck": fck,
        "fy": fy,
        "exposure": exposure,
        "cover_mm": int(cover_mm),
        "service_axial_load_kN": axial_load_kN,
        "factored_axial_load_Pu_kN": Pu_kN,
        "axial_capacity_Pu_kN": Pu_capacity_kN,
        "capacity_utilization": round(Pu_kN / Pu_capacity_kN, 3),
        "steel_required_mm2": steel_calc["governing_Asc_req_mm2"],
        "steel_provided_mm2": Asc_provided,
        "rebar_selected": rebar,
        "lateral_ties": ties,
        "slenderness": slenderness,
        "eccentricity": eccentricity,
        "status": "PASSED" if status == "success" else "NEEDS_REVIEW",
        "approval_status": "STATUS: DRAFT - NOT FOR CONSTRUCTION. Not engineer-reviewed.",
        "citations": [
            "IS 456:2000 Cl. 39.3",
            "IS 456:2000 Cl. 25.1.2",
            "IS 456:2000 Cl. 25.4",
            "IS 456:2000 Cl. 26.5.3.1",
            "IS 456:2000 Cl. 26.5.3.2",
            "IS 456:2000 Table 16",
        ],
    }

    return {
        "status": status,
        "reason": reason,
        "design_dict": design_dict,
        "section_dimensions": f"{int(b_mm)}x{int(D_mm)} mm",
        "width_mm": int(b_mm),
        "depth_mm": int(D_mm),
        "factored_axial_load_Pu_kN": Pu_kN,
        "axial_capacity_Pu_kN": Pu_capacity_kN,
        "rebar_selected": rebar,
        "lateral_ties": ties,
        "checks": {
            "slenderness": slenderness,
            "eccentricity": eccentricity,
        },
        "governing_clauses": design_dict["citations"],
    }
