"""
IS 456:2000 Deterministic Reinforced Concrete Slab Sizing & Design Engine.

Pillar 1: Full Building Frame Members - Floor Slabs (IS 456 Cl. 24 & Cl. 26.5.2).

Covers:
- One-way vs Two-way slab classification (Cl. 24.2)
- Minimum thickness & deflection control (Cl. 23.2.1)
- Factored dead & live loading with concrete unit weight (Cl. 19.2.1)
- Factored bending moments (Cl. 24.1, Table 27)
- Flexural tension reinforcement Ast (Annex G-1.1)
- Minimum reinforcement limits (Cl. 26.5.2.1: 0.12% for Fe 415/Fe 500, 0.15% for Fe 250)
- Maximum bar diameter limits (Cl. 26.5.2.2: phi <= D / 8)
- Maximum bar spacing limits (Cl. 26.5.2.2: min(3d, 300 mm) for main, min(5d, 450 mm) for dist)
- Nominal cover (Table 16 / Cl. 26.4.2)
- Shear capacity check without shear reinforcement (Cl. 40.2.1.1 & Table 19)

Deterministic pure Python only. Zero LLM guessing.
"""

import math
from typing import Dict, Any, Optional, Tuple, List
from src.validation.is456_checks import (
    nominal_cover,
    xu_max_over_d,
)
from src.generation.beam_sizing import lookup_tau_c_table_19



BASE_DISCLAIMER = (
    "Engineering calculations performed in accordance with IS 456:2000. "
    "All outputs are advisory drafts for review by a licensed structural engineer. "
    "NOT FOR IMMEDIATE DIRECT SITE CONSTRUCTION WITHOUT LICENSED SIGN-OFF."
)

TABLE_27_ALPHA = [
    (1.0, 0.062, 0.062),
    (1.1, 0.074, 0.061),
    (1.2, 0.084, 0.059),
    (1.3, 0.093, 0.055),
    (1.4, 0.100, 0.051),
    (1.5, 0.104, 0.046),
    (1.75, 0.113, 0.037),
    (2.0, 0.118, 0.029),
]


def classify_slab(lx_m: float, ly_m: float) -> Tuple[str, float, float]:
    """
    Classifies slab as one-way or two-way per IS 456:2000 Clause 24.2.
    Returns (slab_type, lx_shorter, ly_longer).
    """
    if lx_m <= 0 or ly_m <= 0:
        raise ValueError("Span lengths must be positive numbers.")
    shorter = min(lx_m, ly_m)
    longer = max(lx_m, ly_m)
    ratio = longer / shorter
    slab_type = "one_way" if ratio > 2.0 else "two_way"
    return slab_type, shorter, longer


def get_table_27_coefficients(aspect_ratio: float) -> Tuple[float, float]:
    """
    Interpolates bending moment coefficients alpha_x and alpha_y for simply supported
    two-way slabs from IS 456 Table 27.
    """
    r = max(1.0, min(2.0, aspect_ratio))
    for i in range(len(TABLE_27_ALPHA) - 1):
        r1, ax1, ay1 = TABLE_27_ALPHA[i]
        r2, ax2, ay2 = TABLE_27_ALPHA[i + 1]
        if r1 <= r <= r2:
            frac = (r - r1) / (r2 - r1)
            ax = ax1 + frac * (ax2 - ax1)
            ay = ay1 + frac * (ay2 - ay1)
            return round(ax, 4), round(ay, 4)
    return 0.118, 0.029


def calculate_slab_depth(
    lx_m: float,
    support_condition: str = "simply_supported",
    trial_pt: float = 0.35,
    fy: float = 500.0,
    cover_mm: float = 20.0,
    assumed_bar_dia_mm: float = 10.0,
) -> Tuple[float, float]:
    """
    Determines preliminary effective depth d and total thickness D based on
    deflection control span-to-depth ratios (IS 456 Cl. 23.2.1).
    """
    basic_ratios = {
        "cantilever": 7.0,
        "simply_supported": 20.0,
        "continuous": 26.0,
    }
    basic_ratio = basic_ratios.get(support_condition, 20.0)

    # Modification factor Ft estimation per Fig 4 (Cl. 23.2.1)
    fs = 0.58 * fy * 0.90  # service stress approx
    pt = max(0.15, min(3.0, trial_pt))
    denom = 0.225 + 0.00322 * fs - 0.625 * math.log10(1.0 / pt)
    ft = max(1.0, min(2.0, 1.0 / denom if denom > 0 else 1.3))

    allowable_ratio = basic_ratio * ft
    d_req = (lx_m * 1000.0) / allowable_ratio

    # Practical rounding: minimum thickness for floor slabs is 100 mm, usually 125 mm
    D_tentative = d_req + cover_mm + (assumed_bar_dia_mm / 2.0)
    D_rounded = max(100.0, math.ceil(D_tentative / 10.0) * 10.0)
    d_actual = D_rounded - cover_mm - (assumed_bar_dia_mm / 2.0)

    return d_actual, D_rounded


def get_slab_shear_k_factor(total_depth_mm: float) -> float:
    """
    Returns depth factor k for slabs under shear per IS 456 Clause 40.2.1.1.
    For D <= 150 mm: k = 1.30
    For D >= 300 mm: k = 1.00
    Linear interpolation in-between.
    """
    if total_depth_mm <= 150.0:
        return 1.30
    elif total_depth_mm >= 300.0:
        return 1.00
    else:
        return round(1.30 - (total_depth_mm - 150.0) * (0.30 / 150.0), 3)


def select_slab_rebar(
    ast_req: float,
    d_mm: float,
    D_mm: float,
    is_main_reinforcement: bool = True,
    available_diameters: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """
    Selects optimal rebar diameter and center-to-center spacing satisfying
    IS 456 Cl. 26.5.2.2:
    - phi <= D / 8
    - s <= min(3d, 300 mm) for main steel
    - s <= min(5d, 450 mm) for distribution steel
    """
    if available_diameters is None:
        available_diameters = [8, 10, 12, 16]

    max_phi_allowed = math.floor(D_mm / 8.0)
    valid_diameters = [phi for phi in available_diameters if phi <= max_phi_allowed]
    if not valid_diameters:
        valid_diameters = [min(available_diameters)]

    if is_main_reinforcement:
        max_spacing_allowed = min(3.0 * d_mm, 300.0)
    else:
        max_spacing_allowed = min(5.0 * d_mm, 450.0)

    standard_spacings = [75, 100, 125, 150, 175, 200, 225, 250, 275, 300]
    if not is_main_reinforcement:
        standard_spacings.extend([350, 400, 450])

    candidates = []
    for phi in sorted(valid_diameters):
        a_bar = (math.pi * phi**2) / 4.0
        s_exact = (1000.0 * a_bar) / ast_req

        # Filter standard spacings <= s_exact and <= max_spacing_allowed
        feasible = [s for s in standard_spacings if s <= s_exact and s <= max_spacing_allowed]
        if feasible:
            s_chosen = max(feasible)
            ast_prov = (1000.0 * a_bar) / s_chosen
            waste = ast_prov - ast_req
            candidates.append({
                "bar_dia_mm": phi,
                "spacing_mm": s_chosen,
                "ast_provided": round(ast_prov, 2),
                "ast_required": round(ast_req, 2),
                "waste": waste,
                "callout": f"T{phi} @ {s_chosen} mm c/c",
                "max_spacing_limit": round(max_spacing_allowed, 1),
                "max_dia_limit": max_phi_allowed,
            })

    if not candidates:
        # Fallback to minimum valid dia at 100 mm pitch
        phi = valid_diameters[0]
        a_bar = (math.pi * phi**2) / 4.0
        s_chosen = min(100.0, math.floor(max_spacing_allowed))
        ast_prov = (1000.0 * a_bar) / s_chosen
        return {
            "bar_dia_mm": phi,
            "spacing_mm": int(s_chosen),
            "ast_provided": round(ast_prov, 2),
            "ast_required": round(ast_req, 2),
            "callout": f"T{phi} @ {int(s_chosen)} mm c/c",
            "max_spacing_limit": round(max_spacing_allowed, 1),
            "max_dia_limit": max_phi_allowed,
            "meets_max_spacing": True,
            "meets_max_diameter": phi <= max_phi_allowed,
        }

    # Best candidate has minimum steel surplus
    best = min(candidates, key=lambda c: c["waste"])
    best["meets_max_spacing"] = best["spacing_mm"] <= max_spacing_allowed
    best["meets_max_diameter"] = best["bar_dia_mm"] <= max_phi_allowed
    return best


def size_slab_from_loads(
    lx_m: float,
    ly_m: float,
    live_load_kN_m2: float,
    floor_finish_kN_m2: float = 1.0,
    support_width_mm: float = 230.0,
    fck: float = 25.0,
    fy: float = 500.0,
    exposure: str = "Moderate",
    support_condition: str = "simply_supported",
) -> Dict[str, Any]:
    """
    Full end-to-end deterministic design of reinforced concrete floor slab per IS 456:2000.
    """
    disclaimer = BASE_DISCLAIMER
    citations = [
        "IS 456:2000 Cl. 24.1 (Solid Slabs General)",
        "IS 456:2000 Cl. 24.2 (Slabs Spanning in Two Directions)",
        "IS 456:2000 Cl. 23.2.1 (Deflection Control)",
        "IS 456:2000 Cl. 26.5.2.1 (Minimum Reinforcement)",
        "IS 456:2000 Cl. 26.5.2.2 (Maximum Bar Diameter & Spacing)",
        "IS 456:2000 Cl. 40.2.1.1 (Shear in Slabs)",
        "IS 456:2000 Table 16 (Nominal Cover)",
        "IS 456:2000 Table 19 (Shear Strength of Concrete)",
        "IS 456:2000 Table 27 (Bending Moments in Two-Way Slabs)",
    ]

    # 1. Validation & Classification
    if lx_m <= 0 or ly_m <= 0:
        return {
            "status": "needs_review",
            "reason": "Span dimensions must be greater than zero.",
            "disclaimer": disclaimer,
            "citations": citations,
        }
    if live_load_kN_m2 <= 0:
        return {
            "status": "needs_review",
            "reason": "Live load must be greater than zero.",
            "disclaimer": disclaimer,
            "citations": citations,
        }

    slab_type, lx_shorter, ly_longer = classify_slab(lx_m, ly_m)
    aspect_ratio = round(ly_longer / lx_shorter, 3)

    # 2. Cover lookup (Table 16)
    cover_data = nominal_cover(exposure)
    nominal_cover_mm = float(cover_data["nominal_cover_mm"])

    # 3. Preliminary thickness & effective depth
    d_trial, D_trial = calculate_slab_depth(
        lx_m=lx_shorter,
        support_condition=support_condition,
        fy=fy,
        cover_mm=nominal_cover_mm,
    )

    # 4. Loads per meter strip (b = 1000 mm)
    unit_weight_concrete = 25.0  # kN/m3 (IS 456 Cl. 19.2.1)
    dead_load_kN_m2 = (D_trial / 1000.0) * unit_weight_concrete
    total_service_load_kN_m2 = dead_load_kN_m2 + floor_finish_kN_m2 + live_load_kN_m2
    factored_load_wu_kN_m2 = round(1.5 * total_service_load_kN_m2, 3)

    # 5. Effective span (Cl. 22.2)
    # leff = min(clear_span + d, clear_span + support_width)
    clear_span_x = lx_shorter
    leff_x = min(clear_span_x + (d_trial / 1000.0), clear_span_x + (support_width_mm / 1000.0))
    leff_y = min(ly_longer + (d_trial / 1000.0), ly_longer + (support_width_mm / 1000.0))

    # 6. Bending moments
    b_mm = 1000.0
    if slab_type == "one_way":
        # Mu = wu * leff^2 / 8
        Mu_x_kNm = round((factored_load_wu_kN_m2 * (leff_x ** 2)) / 8.0, 3)
        Mu_y_kNm = 0.0  # transverse direction is distribution only
        alpha_x, alpha_y = None, None
    else:
        # Two-way simply supported using Table 27
        alpha_x, alpha_y = get_table_27_coefficients(aspect_ratio)
        Mu_x_kNm = round(alpha_x * factored_load_wu_kN_m2 * (leff_x ** 2), 3)
        Mu_y_kNm = round(alpha_y * factored_load_wu_kN_m2 * (leff_x ** 2), 3)

    # 7. Check flexural depth requirement (Annex G-1.1)
    xu_max_d = float(xu_max_over_d(fy))
    Q = 0.36 * fck * xu_max_d * (1.0 - 0.42 * xu_max_d)
    Mu_lim_kNm = (Q * b_mm * (d_trial ** 2)) / 1e6

    d_flexure_req = math.sqrt((Mu_x_kNm * 1e6) / (Q * b_mm))
    if d_flexure_req > d_trial:
        d_actual = math.ceil(d_flexure_req / 5.0) * 5.0
        D_actual = max(D_trial, d_actual + nominal_cover_mm + 5.0)
    else:
        d_actual = d_trial
        D_actual = D_trial

    # 8. Minimum reinforcement (Cl. 26.5.2.1)
    # 0.12% for Fe 415/500, 0.15% for Fe 250
    min_pt = 0.0012 if fy >= 415.0 else 0.0015
    ast_min = round(min_pt * b_mm * D_actual, 2)

    # 9. Calculate required tension steel Ast,x (Annex G-1.1)
    # Mu = 0.87 * fy * Ast * d * (1 - (Ast * fy) / (b * d * fck))
    discriminant_x = 1.0 - ((4.6 * Mu_x_kNm * 1e6) / (fck * b_mm * (d_actual ** 2)))
    if discriminant_x < 0:
        return {
            "status": "needs_review",
            "reason": f"Slab section is over-stressed in flexure for Mu = {Mu_x_kNm} kN*m. Increase slab depth.",
            "disclaimer": disclaimer,
            "citations": citations,
        }
    ast_calc_x = (0.5 * fck / fy) * (1.0 - math.sqrt(discriminant_x)) * b_mm * d_actual
    ast_design_x = max(ast_calc_x, ast_min)

    # Select main reinforcement
    main_rebar_x = select_slab_rebar(
        ast_req=ast_design_x,
        d_mm=d_actual,
        D_mm=D_actual,
        is_main_reinforcement=True,
    )

    # 10. Secondary / Transverse Reinforcement
    if slab_type == "one_way":
        ast_dist_req = ast_min
        dist_rebar = select_slab_rebar(
            ast_req=ast_dist_req,
            d_mm=d_actual - main_rebar_x["bar_dia_mm"],
            D_mm=D_actual,
            is_main_reinforcement=False,
        )
        transverse_details = {
            "type": "distribution_temperature_steel",
            "ast_required": ast_dist_req,
            "rebar": dist_rebar,
            "clause": "IS 456 Cl. 26.5.2.1",
        }
    else:
        # Two-way slab: calculate Ast,y along longer span
        d_y = d_actual - main_rebar_x["bar_dia_mm"]
        discriminant_y = 1.0 - ((4.6 * Mu_y_kNm * 1e6) / (fck * b_mm * (d_y ** 2)))
        if discriminant_y < 0:
            ast_calc_y = ast_min
        else:
            ast_calc_y = (0.5 * fck / fy) * (1.0 - math.sqrt(discriminant_y)) * b_mm * d_y
        ast_design_y = max(ast_calc_y, ast_min)
        transverse_rebar = select_slab_rebar(
            ast_req=ast_design_y,
            d_mm=d_y,
            D_mm=D_actual,
            is_main_reinforcement=True,
        )
        transverse_details = {
            "type": "two_way_main_rebar_y",
            "ast_required": round(ast_design_y, 2),
            "rebar": transverse_rebar,
            "Mu_y_kNm": Mu_y_kNm,
            "alpha_y": alpha_y,
            "effective_depth_y_mm": d_y,
            "clause": "IS 456 Table 27 & Cl. 24.2",
        }

    # 11. Deflection Control Verification (Cl. 23.2.1)
    pt_prov = (100.0 * main_rebar_x["ast_provided"]) / (b_mm * d_actual)
    fs = 0.58 * fy * (ast_design_x / main_rebar_x["ast_provided"])
    denom_ft = 0.225 + 0.00322 * fs - 0.625 * math.log10(1.0 / pt_prov)
    ft_verified = max(1.0, min(2.0, 1.0 / denom_ft if denom_ft > 0 else 1.3))
    basic_ratio = 20.0 if support_condition == "simply_supported" else 26.0
    allowable_span_depth = basic_ratio * ft_verified
    actual_span_depth = (leff_x * 1000.0) / d_actual
    deflection_passed = actual_span_depth <= allowable_span_depth

    # 12. Shear Check (Cl. 40.2.1.1 & Table 19)
    # Vu = wu * clear_span / 2
    Vu_kN = round((factored_load_wu_kN_m2 * clear_span_x) / 2.0, 3)
    tau_v = round((Vu_kN * 1000.0) / (b_mm * d_actual), 3)

    tau_c, _, _ = lookup_tau_c_table_19(fck, pt_prov)
    k_factor = get_slab_shear_k_factor(D_actual)
    permissible_tau_c = round(k_factor * tau_c, 3)
    shear_passed = tau_v <= permissible_tau_c

    # Assemble comprehensive design dictionary
    design_dict = {
        "classification": {
            "slab_type": slab_type,
            "aspect_ratio": aspect_ratio,
            "shorter_span_Lx_m": lx_shorter,
            "longer_span_Ly_m": ly_longer,
            "support_condition": support_condition,
        },
        "geometry": {
            "overall_depth_D_mm": D_actual,
            "effective_depth_d_mm": d_actual,
            "nominal_cover_mm": nominal_cover_mm,
            "unit_strip_width_b_mm": b_mm,
            "effective_span_leff_x_m": round(leff_x, 3),
            "effective_span_leff_y_m": round(leff_y, 3),
        },
        "materials": {
            "fck_N_mm2": fck,
            "fy_N_mm2": fy,
            "exposure": exposure,
        },
        "loading": {
            "self_weight_kN_m2": round(dead_load_kN_m2, 2),
            "floor_finish_kN_m2": round(floor_finish_kN_m2, 2),
            "live_load_kN_m2": round(live_load_kN_m2, 2),
            "factored_load_wu_kN_m2": factored_load_wu_kN_m2,
        },
        "flexure": {
            "Mu_x_kNm": Mu_x_kNm,
            "alpha_x": alpha_x,
            "Mu_lim_kNm": round(Mu_lim_kNm, 2),
            "ast_minimum_mm2": ast_min,
            "ast_required_x_mm2": round(ast_design_x, 2),
            "main_rebar_x": main_rebar_x,
            "transverse_reinforcement": transverse_details,
        },
        "checks": {
            "deflection": {
                "actual_span_to_depth": round(actual_span_depth, 2),
                "allowable_span_to_depth": round(allowable_span_depth, 2),
                "modification_factor_Ft": round(ft_verified, 3),
                "passed": deflection_passed,
                "clause": "IS 456 Cl. 23.2.1",
            },
            "shear": {
                "factored_shear_Vu_kN": Vu_kN,
                "nominal_shear_stress_tau_v": tau_v,
                "concrete_shear_strength_tau_c": tau_c,
                "depth_factor_k": k_factor,
                "permissible_shear_stress": permissible_tau_c,
                "passed": shear_passed,
                "clause": "IS 456 Cl. 40.2.1.1 & Table 19",
            },
            "bar_diameter_limit": {
                "max_diameter_allowed_mm": math.floor(D_actual / 8.0),
                "main_bar_dia_mm": main_rebar_x["bar_dia_mm"],
                "passed": main_rebar_x["meets_max_diameter"],
                "clause": "IS 456 Cl. 26.5.2.2 (phi <= D/8)",
            },
            "bar_spacing_limit": {
                "max_spacing_allowed_mm": main_rebar_x["max_spacing_limit"],
                "provided_spacing_mm": main_rebar_x["spacing_mm"],
                "passed": main_rebar_x["meets_max_spacing"],
                "clause": "IS 456 Cl. 26.5.2.2 (s <= min(3d, 300 mm))",
            },
        },
    }

    all_passed = (
        deflection_passed
        and shear_passed
        and main_rebar_x["meets_max_diameter"]
        and main_rebar_x["meets_max_spacing"]
    )

    return {
        "status": "success" if all_passed else "needs_review",
        "slab_type": slab_type,
        "aspect_ratio": round(aspect_ratio, 3),
        "thickness_D_mm": D_actual,
        "effective_depth_d_mm": d_actual,
        "geometry": design_dict["geometry"],
        "flexure": design_dict["flexure"],
        "main_reinforcement": main_rebar_x["callout"],
        "transverse_reinforcement": (
            dist_rebar["callout"]
            if slab_type == "one_way"
            else transverse_details["rebar"]["callout"]
        ),
        "deflection_check": "PASSED" if deflection_passed else "FAILED",
        "shear_check": "PASSED" if shear_passed else "FAILED",
        "checks": design_dict["checks"],
        "governing_clauses": citations,
        "design_dict": design_dict,
        "citations": citations,
        "disclaimer": disclaimer,
    }
