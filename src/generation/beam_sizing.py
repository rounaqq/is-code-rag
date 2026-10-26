"""
Deterministic IS 456:2000 Beam Preliminary Sizing & Load-Based Design Engine.
Computes cross-sectional dimensions (b, D, d), design moments (Mu), shear forces (Vu),
and compliant rebar detailing directly from Span, Dead Load, and Live Load.
Units: mm, N, N/mm2; moments in N*mm (or kNm); spans in meters; loads in kN/m.
No formulas or limits from memory; all derivations follow verified IS 456:2000 clauses and tables.
Does NOT import, read, print, or quote .env or any secret keys.
"""

import json
import math
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

from src.validation.is456_checks import (
    nominal_cover,
    min_tension_steel,
    max_tension_steel,
    max_stirrup_spacing,
    min_shear_steel,
    xu_max_over_d,
    tau_c_max,
    unit_weight_concrete,
    effective_span_simply_supported,
    development_length,
    deflection_check,
    min_bar_clear_spacing,
)

from src.validation.is456_flexure import mu_lim, ast_required_singly
from src.generation.design_validation import validate_design
from src.validation.is456_shear import shear_design

TABLE_19_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "is456_table_19.json"
if not TABLE_19_FILE.exists():
    TABLE_19_FILE = Path("data/processed/is456_table_19.json")


def lookup_tau_c_table_19(fck: float, pt: float) -> Tuple[float, float, str]:
    """
    Looks up design shear strength of concrete tau_c (N/mm2) from Table 19.

    Rule (User assumption, not from IS 456 standard):
    - Row selection: row at or below pt = 100 * Ast / (b * d).
      - If pt < 0.15: first row (pt = 0.15).
      - If pt >= 3.00: last row (pt = 3.00).
    - Grade column mapping from fck:
      - 15 -> M15, 20 -> M20, 25 -> M25, 30 -> M30, 35 -> M35.
      - 40 or more -> 'M40 and above'.

    Returns:
        (tau_c, row_pt_value, grade_column_name)
    """
    grade_val = int(round(fck))
    if grade_val >= 40:
        grade_col = "M40 and above"
    elif grade_val >= 35:
        grade_col = "M35"
    elif grade_val >= 30:
        grade_col = "M30"
    elif grade_val >= 25:
        grade_col = "M25"
    elif grade_val >= 20:
        grade_col = "M20"
    else:
        grade_col = "M15"

    with open(TABLE_19_FILE, "r", encoding="utf-8") as f:
        t19_data = json.load(f)

    rows = t19_data["rows"]
    if pt < 0.15:
        chosen_row = rows[0]
    elif pt >= 3.0:
        chosen_row = rows[-1]
    else:
        eligible = [r for r in rows if r["pt_value"] <= pt]
        chosen_row = eligible[-1] if eligible else rows[0]

    tau_c = float(chosen_row["tau_c"][grade_col])
    return tau_c, float(chosen_row["pt_value"]), grade_col


def select_practical_tension_bars(
    b: float,
    ast_required: float,
    cover_mm: float,
    stirrup_dia: float = 8.0,
    allowed_diameters: Optional[List[int]] = None,
    max_aggregate_size_mm: float = 20.0,
    fck: Optional[float] = None,
    fy: Optional[float] = None,
    d_actual: Optional[float] = None,
    D: Optional[float] = None,
    mu_Nmm: Optional[float] = None,
) -> Tuple[Optional[float], Optional[int], Optional[float]]:
    """
    Selects standard reinforcement bar diameter and count satisfying Ast_required and horizontal clearance.
    Horizontal clearance is checked per IS 456:2000 Cl. 26.3.2(a):
      clear_gap = (b - 2*cover - 2*stirrup_dia - n_bars*bar_dia)/(n_bars - 1) >= max(bar_dia, max_aggregate_size_mm + 5)
    If fck, fy, and D are provided, also verifies under-reinforced section limit per IS 456 Cl. 38.1 & Annex G-1.1(a):
      xu/d = 0.87*fy*Ast_provided / (0.36*fck*b*d_cand) <= xu_max/d
    where d_cand = D - cover - stirrup_dia - bar_dia/2.

    Returns:
        (bar_dia_mm, bar_count, total_area_provided_mm2) or (None, None, None) if no single-layer arrangement fits.
    """
    if allowed_diameters is None:
        allowed_diameters = [12, 16, 20, 25, 32]

    xu_max_d = xu_max_over_d(fy) if fy is not None else None
    valid_candidates = []

    for dia in allowed_diameters:
        bar_area = (math.pi * (dia ** 2)) / 4.0

        if D is not None and mu_Nmm is not None and fck is not None and fy is not None:
            d_cand = D - cover_mm - stirrup_dia - (dia / 2.0)
            flex_cand = ast_required_singly(b=b, d=d_cand, fck=fck, fy=fy, mu=mu_Nmm)
            if flex_cand["status"] != "ok":
                continue
            ast_cand_req = float(flex_cand["ast_mm2"])
            ast_cand_min = (0.85 * b * d_cand) / fy
            target_ast = max(ast_cand_req, ast_cand_min)
        else:
            d_cand = d_actual
            target_ast = ast_required

        min_bars = max(2, math.ceil(target_ast / bar_area))

        # Check maximum 6 bars in a single bottom layer
        for n_bars in range(min_bars, min_bars + 3):
            if n_bars > 6:
                break
            area_provided = n_bars * bar_area
            if area_provided < target_ast:
                continue

            # Check horizontal spacing clearance between bars (IS 456 Cl. 26.3.2(a))
            spacing_res = min_bar_clear_spacing(
                b=b,
                cover_mm=cover_mm,
                stirrup_dia=stirrup_dia,
                n_bars=n_bars,
                bar_dia=float(dia),
                max_aggregate_size_mm=max_aggregate_size_mm,
            )
            if not spacing_res["passed"]:
                continue

            # Check under-reinforced limit: xu/d <= xu_max/d (IS 456 Cl. 38.1 & Annex G-1.1(a))
            if fck is not None and fy is not None and d_cand is not None and xu_max_d is not None:
                xu_d = (0.87 * fy * area_provided) / (0.36 * fck * b * d_cand)
                if xu_d > xu_max_d:
                    continue

            valid_candidates.append({
                "dia": float(dia),
                "n_bars": int(n_bars),
                "area_provided": area_provided,
                "d_cand": d_cand,
            })
            break

    if valid_candidates:
        # Choose arrangement with smallest area (per prompt rule 2)
        valid_candidates.sort(key=lambda c: (c["area_provided"], c["dia"]))
        best = valid_candidates[0]
        return best["dia"], best["n_bars"], best["area_provided"]

    return None, None, None



def size_beam_from_loads(
    span_m: float,
    dead_load_kN_per_m: float = 0.0,
    live_load_kN_per_m: float = 0.0,
    fck: float = 25.0,
    fy: float = 500.0,
    exposure: str = "Moderate",
    b: Optional[float] = None,
    support_width_mm: float = 300.0,
    include_self_weight: bool = True,
    max_aggregate_size_mm: float = 20.0,
) -> Dict[str, Any]:
    """
    Sizes cross-sectional dimensions (b, D, d), evaluates design moments (Mu),
    shear forces (Vu), and determines IS 456 compliant reinforcement from span and loads.

    IS 456:2000 Clauses & Tables:
        - Cl. 22.2: Effective Span
        - Cl. 23.2.1: Deflection Control (Span-to-depth ratio)
        - Cl. 36.4.1 & Table 18: Partial safety factor for loads (1.5 DL + 1.5 LL)
        - Cl. 38.1 & Annex G: Flexural capacity and limiting depth of neutral axis
        - Cl. 40.1 & Table 20: Maximum shear stress tau_c_max
        - Cl. 26.5.1: Minimum & maximum reinforcement limits
        - Table 16: Nominal cover for exposure conditions
    """
    if span_m <= 0:
        raise ValueError("Span must be strictly positive.")
    if dead_load_kN_per_m < 0 or live_load_kN_per_m < 0:
        raise ValueError("Applied dead and live loads must be non-negative.")
    if dead_load_kN_per_m + live_load_kN_per_m <= 0:
        raise ValueError("Total applied service load must be greater than zero.")
    if fck <= 0 or fy <= 0:
        raise ValueError("Concrete fck and steel fy must be positive.")

    # 1. Cover from Table 16
    cover_res = nominal_cover(exposure)
    cover_mm = float(cover_res["required"])

    # 2. Determine Beam Width b (mm)
    # Standard Indian architectural masonry widths: 230 mm or 300 mm
    if b is not None:
        if b <= 0:
            raise ValueError("Beam width b must be positive.")
        b_val = float(b)
    else:
        b_val = 300.0 if span_m >= 5.0 else 230.0

    # 3. Preliminary Effective Depth d_trial (IS 456 Cl. 23.2.1)
    # Basic L/d = 20 for simply supported beams up to 10 m.
    # Trial ratio L/d approx 12 to 15 considering serviceability and tension modification.
    span_mm = span_m * 1000.0
    trial_d_raw = span_mm / 14.0
    # Round up to multiple of 25 mm, min 200 mm
    d_trial = max(200.0, math.ceil(trial_d_raw / 25.0) * 25.0)
    D_trial = d_trial + cover_mm + 25.0
    D_trial = math.ceil(D_trial / 25.0) * 25.0

    # 4. Self-Weight & Factored Load Calculation (IS 456 Cl. 19.2.1 / Cl. 36.4.1 / Table 18)
    # Reinforced concrete unit weight per IS 456:2000 Cl. 19.2.1 (25.0 kN/m3)
    gamma_c = unit_weight_concrete("reinforced")
    w_self = (gamma_c * (b_val / 1000.0) * (D_trial / 1000.0)) if include_self_weight else 0.0
    w_dl_total = dead_load_kN_per_m + w_self
    w_ll_total = live_load_kN_per_m
    w_service = w_dl_total + w_ll_total

    # Factored load wu = 1.5 * (DL + LL)
    w_u = 1.5 * w_service  # kN/m = N/mm

    # 5. Effective Span L_eff (IS 456 Cl. 22.2(a))
    # Lesser of: (clear span + d) or (center to center of supports = clear span + support_width)
    clear_span_mm = span_mm
    eff_span_res = effective_span_simply_supported(
        clear_span_mm=clear_span_mm,
        d_mm=d_trial,
        support_width_mm=support_width_mm,
    )
    l_eff_m = float(eff_span_res["effective_span_m"])

    # 6. Factored Bending Moment & Shear Force (Simply Supported)
    # Mu = wu * Leff^2 / 8  (kN*m)
    # Vu = wu * Leff / 2     (kN)
    mu_kNm = (w_u * (l_eff_m ** 2)) / 8.0
    mu_Nmm = mu_kNm * 1e6
    vu_kN = (w_u * l_eff_m) / 2.0
    vu_N = vu_kN * 1e3

    # 7. Limiting Flexural Capacity & Required Depth (IS 456 Annex G-1.1 & Cl. 38.1)
    xu_max_d = xu_max_over_d(fy)
    r_lim = 0.36 * xu_max_d * (1.0 - 0.42 * xu_max_d) * fck
    d_min_flexure = math.sqrt(mu_Nmm / (r_lim * b_val))

    # Adopt effective depth satisfying both deflection and flexure
    d_adopted = max(d_trial, d_min_flexure)
    d_adopted = math.ceil(d_adopted / 25.0) * 25.0
    D_adopted = math.ceil((d_adopted + cover_mm + 25.0) / 25.0) * 25.0

    # Re-evaluate self weight with adopted depth if changed significantly
    if D_adopted != D_trial and include_self_weight:
        w_self = gamma_c * (b_val / 1000.0) * (D_adopted / 1000.0)
        w_service = dead_load_kN_per_m + w_self + live_load_kN_per_m
        w_u = 1.5 * w_service
        eff_span_res = effective_span_simply_supported(
            clear_span_mm=clear_span_mm,
            d_mm=d_adopted,
            support_width_mm=support_width_mm,
        )
        l_eff_m = float(eff_span_res["effective_span_m"])
        mu_kNm = (w_u * (l_eff_m ** 2)) / 8.0
        mu_Nmm = mu_kNm * 1e6
        vu_kN = (w_u * l_eff_m) / 2.0
        vu_N = vu_kN * 1e3

    # 8. Required Tension Steel Ast (Annex G-1.1(b))
    flexure_res = ast_required_singly(b=b_val, d=d_adopted, fck=fck, fy=fy, mu=mu_Nmm)
    if flexure_res["status"] != "ok":
        # If still exceeding mu_lim, adjust d to be singly reinforced
        d_min_needed = math.sqrt(mu_Nmm / (r_lim * b_val)) + 25.0
        d_adopted = math.ceil(d_min_needed / 25.0) * 25.0
        D_adopted = math.ceil((d_adopted + cover_mm + 25.0) / 25.0) * 25.0
        flexure_res = ast_required_singly(b=b_val, d=d_adopted, fck=fck, fy=fy, mu=mu_Nmm)

    ast_calc = float(flexure_res["ast_mm2"])
    xu_d_calc = float(flexure_res["xu_over_d"])
    mu_lim_val = float(flexure_res["mu_lim"])

    # Tension steel boundaries (IS 456 Cl. 26.5.1.1)
    ast_min = (0.85 * b_val * d_adopted) / fy
    ast_max = 0.04 * b_val * D_adopted
    ast_target = max(ast_calc, ast_min)

    # 9. Shear Stress & Maximum Limit (IS 456 Cl. 40.1 & Table 20)
    tau_v = vu_N / (b_val * d_adopted)
    concrete_grade_str = f"M{int(round(fck))}"
    tau_c_limit = tau_c_max(concrete_grade_str)
    shear_acceptable = tau_v <= tau_c_limit

    practical_dia_note = (
        "Stirrup size selection (trying 8 mm, then 10 mm, then 12 mm and taking the first "
        "that gives a calculated spacing of at least 100 mm) is a practical rule and not from IS 456."
    )
    support_face_vu_note = (
        "Vu is taken at the support face without the reduction allowed by IS 456:2000 Cl. 40.5.3."
    )
    ast_provided_tension_note = (
        "ast_provided is taken as the full tension steel; IS 456 Table 19 note requires steel "
        "continuing at least d beyond the section and full anchorage, which is not implemented by this tool."
    )

    if not shear_acceptable:
        reason = (
            f"section_too_small: Nominal shear stress tau_v ({tau_v:.3f} N/mm2) "
            f"exceeds maximum permissible tau_c_max ({tau_c_limit:.3f} N/mm2) "
            f"per IS 456:2000 Cl. 40.2.3 and Table 20. Cross-section dimensions (b and/or d) must be increased."
        )
        review_notes = [
            "20 mm nominal maximum aggregate size assumed unless provided",
            "Table 19 row selection rule (row at or below pt, first row if pt < 0.15, last row if pt >= 3.0) is an assumption, not from the IS 456 standard.",
            support_face_vu_note,
            ast_provided_tension_note,
            practical_dia_note,
        ]
        return {
            "status": "needs_review",
            "reason": reason,
            "shear_status": "needs_review",
            "inputs": {
                "span_m": span_m,
                "dead_load_kN_per_m": dead_load_kN_per_m,
                "live_load_kN_per_m": live_load_kN_per_m,
                "fck": fck,
                "fy": fy,
                "exposure": exposure,
                "support_width_mm": support_width_mm,
                "max_aggregate_size_mm": max_aggregate_size_mm,
            },
            "derived_loads": {
                "self_weight_kN_per_m": round(w_self, 3),
                "total_service_load_kN_per_m": round(w_service, 3),
                "factored_load_wu_kN_per_m": round(w_u, 3),
                "effective_span_m": round(l_eff_m, 3),
                "factored_moment_Mu_kNm": round(mu_kNm, 3),
                "factored_shear_Vu_kN": round(vu_kN, 3),
            },
            "section_dimensions": {
                "b": b_val,
                "D": D_adopted,
                "d": d_adopted,
                "d_actual": d_adopted,
                "d_trial": d_trial,
                "d_adopted": d_adopted,
                "cover_mm": cover_mm,
            },
            "flexure": {
                "ast_calculated_mm2": round(ast_calc, 2),
                "ast_min_mm2": round(ast_min, 2),
                "ast_max_mm2": round(ast_max, 2),
                "ast_design_mm2": round(ast_target, 2),
                "mu_lim_kNm": round(mu_lim_val / 1e6, 3),
                "xu_over_d": round(xu_d_calc, 3),
            },
            "shear": {
                "status": "needs_review",
                "reason": reason,
                "notes": review_notes,
                "nominal_shear_stress_tau_v": round(tau_v, 3),
                "tau_c_max": tau_c_limit,
            },
            "notes": review_notes,
        }

    # 10. Practical Reinforcement Detailing Selection
    # Bar selection checked per IS 456 Cl. 26.3.2(a) and under-reinforced limit (stirrup_dia=8.0 used for clearance calculation)
    main_bar_dia, main_bar_count, ast_provided = select_practical_tension_bars(
        b=b_val,
        ast_required=ast_target,
        cover_mm=cover_mm,
        stirrup_dia=8.0,
        max_aggregate_size_mm=max_aggregate_size_mm,
        fck=fck,
        fy=fy,
        D=D_adopted,
        mu_Nmm=mu_Nmm,
    )

    if main_bar_dia is None:
        reason = (
            f"insufficient_bar_clear_spacing_or_over_reinforced: No single-layer bar arrangement in standard list "
            f"([12, 16, 20, 25, 32] mm, max 6 bars) satisfies flexure, minimum horizontal clear distance "
            f"per IS 456:2000 Cl. 26.3.2(a) (clear gap >= max(bar_dia, {max_aggregate_size_mm:.1f} + 5 mm)), "
            f"and under-reinforced limit (xu/d <= xu_max/d per Cl. 38.1) for Ast_required = {ast_target:.2f} mm2. "
            f"Cross-section width b ({b_val} mm) may need to be increased or multiple layers used."
        )
        review_notes = [
            "20 mm nominal maximum aggregate size assumed unless provided",
            "Table 19 row selection rule (row at or below pt, first row if pt < 0.15, last row if pt >= 3.0) is an assumption, not from the IS 456 standard.",
            "Vu is taken at the support face without the reduction allowed by IS 456:2000 Cl. 40.5.3.",
            "ast_provided is taken as the full tension steel; IS 456 Table 19 note requires steel continuing at least d beyond the section and full anchorage, which is not implemented by this tool.",
            "Stirrup size selection (trying 8 mm, then 10 mm, then 12 mm and taking the first that gives a calculated spacing of at least 100 mm) is a practical rule and not from IS 456.",
        ]
        return {
            "status": "needs_review",
            "reason": reason,
            "shear_status": "needs_review",
            "inputs": {
                "span_m": span_m,
                "dead_load_kN_per_m": dead_load_kN_per_m,
                "live_load_kN_per_m": live_load_kN_per_m,
                "fck": fck,
                "fy": fy,
                "exposure": exposure,
                "support_width_mm": support_width_mm,
                "max_aggregate_size_mm": max_aggregate_size_mm,
            },
            "derived_loads": {
                "self_weight_kN_per_m": round(w_self, 3),
                "total_service_load_kN_per_m": round(w_service, 3),
                "factored_load_wu_kN_per_m": round(w_u, 3),
                "effective_span_m": round(l_eff_m, 3),
                "factored_moment_Mu_kNm": round(mu_kNm, 3),
                "factored_shear_Vu_kN": round(vu_kN, 3),
            },
            "section_dimensions": {
                "b": b_val,
                "D": D_adopted,
                "d": d_adopted,
                "d_actual": d_adopted,
                "d_trial": d_trial,
                "d_adopted": d_adopted,
                "cover_mm": cover_mm,
            },
            "flexure": {
                "ast_calculated_mm2": round(ast_calc, 2),
                "ast_min_mm2": round(ast_min, 2),
                "ast_max_mm2": round(ast_max, 2),
                "ast_design_mm2": round(ast_target, 2),
                "mu_lim_kNm": round(mu_lim_val / 1e6, 3),
                "xu_over_d": round(xu_d_calc, 3),
            },
            "shear": {"status": "needs_review", "reason": reason, "notes": review_notes, "nominal_shear_stress_tau_v": round(tau_v, 3)},
            "notes": review_notes,
        }

    d_actual = D_adopted - cover_mm - 8.0 - (main_bar_dia / 2.0)

    # 10b. Iterative Refinement Loop (up to 5 passes) per IS 456 Annex G-1.1 & Cl. 26.3.2 / Cl. 38.1
    # After bars and d_actual are chosen, recompute Ast_required at d_actual (G-1.1(b)),
    # re-select bars with the same rules (including Cl. 26.3.2 and xu/d <= xu_max/d),
    # and repeat until bars and d_actual stop changing (at most 5 passes).
    converged = False
    loop_passes = 0
    for iteration in range(1, 6):
        loop_passes = iteration
        flex_iter = ast_required_singly(b=b_val, d=d_actual, fck=fck, fy=fy, mu=mu_Nmm)
        if flex_iter["status"] != "ok":
            reason = (
                f"flexure_exceeded_mu_lim: Section at d_actual ({d_actual:.1f} mm) "
                f"exceeds limiting moment capacity mu_lim per IS 456 Annex G-1.1."
            )
            return {
                "status": "needs_review",
                "reason": reason,
                "shear_status": "needs_review",
                "inputs": {
                    "span_m": span_m,
                    "dead_load_kN_per_m": dead_load_kN_per_m,
                    "live_load_kN_per_m": live_load_kN_per_m,
                    "fck": fck,
                    "fy": fy,
                    "exposure": exposure,
                    "support_width_mm": support_width_mm,
                    "max_aggregate_size_mm": max_aggregate_size_mm,
                },
                "derived_loads": {
                    "self_weight_kN_per_m": round(w_self, 3),
                    "total_service_load_kN_per_m": round(w_service, 3),
                    "factored_load_wu_kN_per_m": round(w_u, 3),
                    "effective_span_m": round(l_eff_m, 3),
                    "factored_moment_Mu_kNm": round(mu_kNm, 3),
                    "factored_shear_Vu_kN": round(vu_kN, 3),
                },
                "section_dimensions": {
                    "b": b_val,
                    "D": D_adopted,
                    "d": d_actual,
                    "d_actual": d_actual,
                    "d_trial": d_trial,
                    "d_adopted": d_adopted,
                    "cover_mm": cover_mm,
                },
                "flexure": {
                    "ast_calculated_mm2": round(ast_calc, 2),
                    "ast_min_mm2": round(ast_min, 2),
                    "ast_max_mm2": round(ast_max, 2),
                    "ast_design_mm2": round(ast_target, 2),
                    "mu_lim_kNm": round(mu_lim_val / 1e6, 3),
                    "xu_over_d": round(xu_d_calc, 3),
                },
                "shear": {"status": "needs_review", "reason": reason, "notes": review_notes, "nominal_shear_stress_tau_v": round(tau_v, 3)},
                "notes": review_notes,
            }

        ast_calc_iter = float(flex_iter["ast_mm2"])
        ast_min_iter = (0.85 * b_val * d_actual) / fy
        ast_target_iter = max(ast_calc_iter, ast_min_iter)

        next_dia, next_count, next_ast = select_practical_tension_bars(
            b=b_val,
            ast_required=ast_target_iter,
            cover_mm=cover_mm,
            stirrup_dia=8.0,
            max_aggregate_size_mm=max_aggregate_size_mm,
            fck=fck,
            fy=fy,
            D=D_adopted,
            mu_Nmm=mu_Nmm,
        )

        if next_dia is None:
            reason = (
                f"insufficient_bar_clear_spacing_or_over_reinforced: No single-layer bar arrangement in standard list "
                f"satisfies flexure, minimum horizontal clear distance (IS 456 Cl. 26.3.2(a)), and "
                f"under-reinforced limit (xu/d <= xu_max/d per Cl. 38.1)."
            )
            return {
                "status": "needs_review",
                "reason": reason,
                "shear_status": "needs_review",
                "inputs": {
                    "span_m": span_m,
                    "dead_load_kN_per_m": dead_load_kN_per_m,
                    "live_load_kN_per_m": live_load_kN_per_m,
                    "fck": fck,
                    "fy": fy,
                    "exposure": exposure,
                    "support_width_mm": support_width_mm,
                    "max_aggregate_size_mm": max_aggregate_size_mm,
                },
                "derived_loads": {
                    "self_weight_kN_per_m": round(w_self, 3),
                    "total_service_load_kN_per_m": round(w_service, 3),
                    "factored_load_wu_kN_per_m": round(w_u, 3),
                    "effective_span_m": round(l_eff_m, 3),
                    "factored_moment_Mu_kNm": round(mu_kNm, 3),
                    "factored_shear_Vu_kN": round(vu_kN, 3),
                },
                "section_dimensions": {
                    "b": b_val,
                    "D": D_adopted,
                    "d": d_actual,
                    "d_actual": d_actual,
                    "d_trial": d_trial,
                    "d_adopted": d_adopted,
                    "cover_mm": cover_mm,
                },
                "flexure": {
                    "ast_calculated_mm2": round(ast_calc, 2),
                    "ast_min_mm2": round(ast_min, 2),
                    "ast_max_mm2": round(ast_max, 2),
                    "ast_design_mm2": round(ast_target, 2),
                    "mu_lim_kNm": round(mu_lim_val / 1e6, 3),
                    "xu_over_d": round(xu_d_calc, 3),
                },
                "shear": {"status": "needs_review", "reason": reason, "notes": review_notes, "nominal_shear_stress_tau_v": round(tau_v, 3)},
                "notes": review_notes,
            }

        next_d_actual = D_adopted - cover_mm - 8.0 - (next_dia / 2.0)

        if (
            next_dia == main_bar_dia
            and next_count == main_bar_count
            and abs(next_d_actual - d_actual) < 1e-4
        ):
            converged = True
            main_bar_dia = next_dia
            main_bar_count = next_count
            ast_provided = next_ast
            d_actual = next_d_actual
            ast_calc = ast_calc_iter
            ast_min = ast_min_iter
            ast_target = ast_target_iter
            xu_d_calc = float(flex_iter["xu_over_d"])
            break

        main_bar_dia = next_dia
        main_bar_count = next_count
        ast_provided = next_ast
        d_actual = next_d_actual
        ast_calc = ast_calc_iter
        ast_min = ast_min_iter
        ast_target = ast_target_iter
        xu_d_calc = float(flex_iter["xu_over_d"])

    if not converged:
        reason = (
            "reinforcement_loop_did_not_converge: Reinforcement detailing and d_actual "
            "did not converge within 5 passes."
        )
        return {
            "status": "needs_review",
            "reason": reason,
            "shear_status": "needs_review",
            "inputs": {
                "span_m": span_m,
                "dead_load_kN_per_m": dead_load_kN_per_m,
                "live_load_kN_per_m": live_load_kN_per_m,
                "fck": fck,
                "fy": fy,
                "exposure": exposure,
                "support_width_mm": support_width_mm,
                "max_aggregate_size_mm": max_aggregate_size_mm,
            },
            "derived_loads": {
                "self_weight_kN_per_m": round(w_self, 3),
                "total_service_load_kN_per_m": round(w_service, 3),
                "factored_load_wu_kN_per_m": round(w_u, 3),
                "effective_span_m": round(l_eff_m, 3),
                "factored_moment_Mu_kNm": round(mu_kNm, 3),
                "factored_shear_Vu_kN": round(vu_kN, 3),
            },
            "section_dimensions": {
                "b": b_val,
                "D": D_adopted,
                "d": d_actual,
                "d_actual": d_actual,
                "d_trial": d_trial,
                "d_adopted": d_adopted,
                "cover_mm": cover_mm,
            },
            "flexure": {
                "ast_calculated_mm2": round(ast_calc, 2),
                "ast_min_mm2": round(ast_min, 2),
                "ast_max_mm2": round(ast_max, 2),
                "ast_design_mm2": round(ast_target, 2),
                "mu_lim_kNm": round(mu_lim_val / 1e6, 3),
                "xu_over_d": round(xu_d_calc, 3),
            },
            "shear": {"status": "needs_review", "reason": reason, "notes": review_notes, "nominal_shear_stress_tau_v": round(tau_v, 3)},
            "notes": review_notes,
        }

    # Top compression / hanger bars (2 bars to hold shear stirrups)
    comp_dia = 12.0 if D_adopted >= 450.0 else 10.0
    comp_count = 2

    # 11. Deterministic Shear Design (IS 456 Cl. 40, Cl. 26.5.1.5, Cl. 26.5.1.6, Tables 19 & 20)
    # Practical rule (not from IS 456): try stirrup diameter 8, then 10, then 12 mm
    # and take the first that gives a calculated spacing of at least 100 mm.
    practical_dia_note = (
        "Stirrup size selection (trying 8 mm, then 10 mm, then 12 mm and taking the first "
        "that gives a calculated spacing of at least 100 mm) is a practical rule and not from IS 456."
    )
    support_face_vu_note = (
        "Vu is taken at the support face without the reduction allowed by IS 456:2000 Cl. 40.5.3."
    )
    ast_provided_tension_note = (
        "ast_provided is taken as the full tension steel; IS 456 Table 19 note requires steel "
        "continuing at least d beyond the section and full anchorage, which is not implemented by this tool."
    )

    chosen_shear_res = None
    chosen_dia = None
    chosen_d_actual = None
    for trial_dia in [8.0, 10.0, 12.0]:
        d_actual_trial = D_adopted - cover_mm - trial_dia - (main_bar_dia / 2.0)
        s_res = shear_design(
            b=b_val,
            d=d_actual_trial,
            fck=fck,
            fy_stirrup=fy,
            vu=vu_N,
            ast_provided=ast_provided,
            stirrup_dia=trial_dia,
            legs=2,
        )
        if s_res["status"] == "section_too_small":
            chosen_shear_res = s_res
            chosen_d_actual = d_actual_trial
            break
        # Take the first that gives a calculated spacing of at least 100 mm
        if s_res.get("spacing_mm") is not None and s_res["spacing_mm"] >= 100.0:
            chosen_shear_res = s_res
            chosen_dia = trial_dia
            chosen_d_actual = d_actual_trial
            break

    # If none works, or the status is "section_too_small", return status "needs_review"
    # with the reason and do not produce a finished design.
    d_actual_fallback = chosen_d_actual if chosen_d_actual is not None else (D_adopted - cover_mm - 8.0 - (main_bar_dia / 2.0))
    if chosen_dia is None or (chosen_shear_res and chosen_shear_res["status"] == "section_too_small"):
        if chosen_shear_res and chosen_shear_res["status"] == "section_too_small":
            reason = (
                f"section_too_small: Nominal shear stress tau_v ({chosen_shear_res['tau_v']:.3f} N/mm2) "
                f"exceeds maximum permissible tau_c_max ({chosen_shear_res['tau_c_max']:.3f} N/mm2) "
                f"per IS 456:2000 Cl. 40.2.3 and Table 20. Cross-section dimensions (b and/or d) must be increased."
            )
        else:
            reason = (
                "stirrup_spacing_below_100mm: Calculated stirrup spacing for 8 mm, 10 mm, and 12 mm bars "
                "is below 100 mm. Practical minimum spacing not met."
            )

        review_notes = [
            "20 mm nominal maximum aggregate size assumed unless provided",
            "Table 19 row selection rule (row at or below pt, first row if pt < 0.15, last row if pt >= 3.0) is an assumption, not from the IS 456 standard.",
            support_face_vu_note,
            ast_provided_tension_note,
            practical_dia_note,
        ]
        if chosen_shear_res and chosen_shear_res.get("notes"):
            for n in chosen_shear_res["notes"]:
                if n not in review_notes:
                    review_notes.append(n)

        return {
            "status": "needs_review",
            "reason": reason,
            "shear_status": "needs_review",
            "inputs": {
                "span_m": span_m,
                "dead_load_kN_per_m": dead_load_kN_per_m,
                "live_load_kN_per_m": live_load_kN_per_m,
                "fck": fck,
                "fy": fy,
                "exposure": exposure,
                "support_width_mm": support_width_mm,
                "max_aggregate_size_mm": max_aggregate_size_mm,
            },
            "derived_loads": {
                "self_weight_kN_per_m": round(w_self, 3),
                "total_service_load_kN_per_m": round(w_service, 3),
                "factored_load_wu_kN_per_m": round(w_u, 3),
                "effective_span_m": round(l_eff_m, 3),
                "factored_moment_Mu_kNm": round(mu_kNm, 3),
                "factored_shear_Vu_kN": round(vu_kN, 3),
            },
            "section_dimensions": {
                "b": b_val,
                "D": D_adopted,
                "d": d_actual_fallback,
                "d_actual": d_actual_fallback,
                "d_trial": d_trial,
                "d_adopted": d_adopted,
                "cover_mm": cover_mm,
            },
            "flexure": {
                "ast_calculated_mm2": round(ast_calc, 2),
                "ast_min_mm2": round(ast_min, 2),
                "ast_max_mm2": round(ast_max, 2),
                "ast_design_mm2": round(ast_target, 2),
                "mu_lim_kNm": round(mu_lim_val / 1e6, 3),
                "xu_over_d": round(xu_d_calc, 3),
            },
            "shear": dict(chosen_shear_res, nominal_shear_stress_tau_v=round(chosen_shear_res["tau_v"], 3)) if chosen_shear_res else {"status": "needs_review", "reason": reason, "notes": review_notes, "nominal_shear_stress_tau_v": round(tau_v, 3)},
            "notes": review_notes,
        }

    stirrup_dia = float(chosen_dia)
    d_actual = chosen_d_actual
    # Use the suggested_spacing_mm (rounded down to 5 mm) in the drawing.
    stirrup_spacing = float(chosen_shear_res["suggested_spacing_mm"])
    shear_status = chosen_shear_res["status"]
    tau_v = chosen_shear_res["tau_v"]
    tau_c = chosen_shear_res["tau_c"]
    vus = chosen_shear_res.get("vus")
    tau_c_limit = chosen_shear_res["tau_c_max"]

    shear_notes = [
        "20 mm nominal maximum aggregate size assumed unless provided",
        "Table 19 row selection rule (row at or below pt, first row if pt < 0.15, last row if pt >= 3.0) is an assumption, not from the IS 456 standard.",
        support_face_vu_note,
        ast_provided_tension_note,
        practical_dia_note,
    ]
    if chosen_shear_res.get("notes"):
        for n in chosen_shear_res["notes"]:
            if n not in shear_notes:
                shear_notes.append(n)

    # 12. Deflection Control Check (IS 456 Cl. 23.2.1; F1 is an approximate curve fit, not from IS 456)
    deflection_res = deflection_check(
        span_m=l_eff_m,
        d_actual_mm=d_actual,
        fy=fy,
        ast_required_mm2=ast_calc,
        ast_provided_mm2=ast_provided,
        b_mm=b_val,
        member_type="simply_supported",
    )
    conservative_note = "Effective span used for L/d (conservative); wording of Cl. 23.2.1 not re-checked against the page"
    if "notes" in deflection_res and conservative_note not in deflection_res["notes"]:
        deflection_res["notes"].append(conservative_note)
    deflection_res["note"] = f"{deflection_res.get('note', '')} {conservative_note}".strip()

    # 13. Development Length Calculation (IS 456 Cl. 26.2.1, 26.2.1.1, 26.2.3.3)
    ld_res = development_length(
        bar_dia_mm=main_bar_dia,
        fck=fck,
        fy=fy,
        bar_type="deformed",
        stress_type="tension",
    )

    design_dict = {
        "b": b_val,
        "D": D_adopted,
        "d": d_actual,
        "d_actual": d_actual,
        "d_trial": d_trial,
        "d_adopted": d_adopted,
        "fck": fck,
        "fy": fy,
        "exposure": exposure,
        "main_bar_dia_mm": main_bar_dia,
        "main_bar_count": main_bar_count,
        "stirrup_dia_mm": stirrup_dia,
        "stirrup_spacing_mm": stirrup_spacing,
        "compression_bar_dia_mm": comp_dia,
        "compression_bar_count": comp_count,
        "shear_status": shear_status,
        "tau_v": round(tau_v, 3),
        "tau_c": round(tau_c, 3),
        "vus": round(vus, 2) if vus is not None else 0.0,
        "ld_mm": ld_res["ld_rounded_mm"],
        "max_aggregate_size_mm": max_aggregate_size_mm,
        "shear_notes": shear_notes,
        "loop_passes": loop_passes,
    }

    return {
        "status": "ok",
        "inputs": {
            "span_m": span_m,
            "dead_load_kN_per_m": dead_load_kN_per_m,
            "live_load_kN_per_m": live_load_kN_per_m,
            "fck": fck,
            "fy": fy,
            "exposure": exposure,
            "support_width_mm": support_width_mm,
            "max_aggregate_size_mm": max_aggregate_size_mm,
        },
        "derived_loads": {
            "self_weight_kN_per_m": round(w_self, 3),
            "total_service_load_kN_per_m": round(w_service, 3),
            "factored_load_wu_kN_per_m": round(w_u, 3),
            "effective_span_m": round(l_eff_m, 3),
            "factored_moment_Mu_kNm": round(mu_kNm, 3),
            "factored_shear_Vu_kN": round(vu_kN, 3),
        },
        "section_dimensions": {
            "b": b_val,
            "D": D_adopted,
            "d": d_actual,
            "d_actual": d_actual,
            "d_trial": d_trial,
            "d_adopted": d_adopted,
            "cover_mm": cover_mm,
        },
        "flexure": {
            "ast_calculated_mm2": round(ast_calc, 2),
            "ast_min_mm2": round(ast_min, 2),
            "ast_max_mm2": round(ast_max, 2),
            "ast_design_mm2": round(ast_target, 2),
            "mu_lim_kNm": round(mu_lim_val / 1e6, 3),
            "xu_over_d": round(xu_d_calc, 3),
        },
        "shear": {
            "nominal_shear_stress_tau_v": round(tau_v, 3),
            "tau_c": round(tau_c, 3),
            "tau_c_max": tau_c_limit,
            "pt": round(chosen_shear_res["pt"], 3),
            "vus": round(vus, 2) if vus is not None else None,
            "asv": round(chosen_shear_res["asv"], 2),
            "sv_calc": round(chosen_shear_res["sv_calc"], 2) if chosen_shear_res.get("sv_calc") else None,
            "sv_min_steel": round(chosen_shear_res["sv_min_steel"], 2),
            "sv_cap": round(chosen_shear_res["sv_cap"], 2),
            "spacing_calc_mm": round(chosen_shear_res["spacing_mm"], 2),
            "suggested_spacing_mm": stirrup_spacing,
            "shear_safe": shear_acceptable,
            "shear_status": shear_status,
            "citations": chosen_shear_res.get("citations", []),
            "notes": shear_notes,
        },
        "shear_status": shear_status,
        "deflection": deflection_res,
        "development_length": ld_res,
        "reinforcement_detailing": {
            "main_bar_dia_mm": main_bar_dia,
            "main_bar_count": main_bar_count,
            "main_bar_area_provided_mm2": round(ast_provided, 2),
            "compression_bar_dia_mm": comp_dia,
            "compression_bar_count": comp_count,
            "stirrup_dia_mm": stirrup_dia,
            "stirrup_legs": 2,
            "stirrup_spacing_mm": stirrup_spacing,
            "loop_passes": loop_passes,
        },
        "design_dict": design_dict,
        "notes": [
            "20 mm nominal maximum aggregate size assumed unless provided",
        ] + shear_notes,
        "is456_citations": [
            "IS 456:2000 Cl. 19.2.1",
            "IS 456:2000 Cl. 22.2(a)",
            "IS 456:2000 Cl. 23.2.1",
            "IS 456:2000 Cl. 26.2.1",
            "IS 456:2000 Cl. 26.2.1.1",
            "IS 456:2000 Cl. 26.2.3.3",
            "IS 456:2000 Cl. 26.3.2(a)",
            "IS 456:2000 Cl. 36.4",
            "IS 456:2000 Cl. 38.1",
            "IS 456:2000 Annex G, G-1.1",
            "IS 456:2000 Cl. 26.5.1.1",
            "IS 456:2000 Cl. 26.5.1.5",
            "IS 456:2000 Cl. 26.5.1.6",
            "IS 456:2000 Table 16",
            "IS 456:2000 Table 19",
            "IS 456:2000 Table 20",
            "IS 456:2000 Cl. 40.1",
            "IS 456:2000 Cl. 40.2.3",
            "IS 456:2000 Cl. 40.3",
            "IS 456:2000 Cl. 40.4",
            "IS 456:2000 Cl. 40.4(a)",
        ],
    }


def design_and_validate_beam(
    span_m: float,
    dead_load_kN_per_m: float = 0.0,
    live_load_kN_per_m: float = 0.0,
    fck: float = 25.0,
    fy: float = 500.0,
    exposure: str = "Moderate",
    b: Optional[float] = None,
    support_width_mm: float = 300.0,
    max_aggregate_size_mm: float = 20.0,
) -> Dict[str, Any]:
    """
    Complete end-to-end beam design workflow:
    1. Sizes the beam from Span and Load.
    2. Determines compliant rebar detailing.
    3. Runs deterministic IS 456 code validation checks with citations and clause texts.
    """
    sizing_res = size_beam_from_loads(
        span_m=span_m,
        dead_load_kN_per_m=dead_load_kN_per_m,
        live_load_kN_per_m=live_load_kN_per_m,
        fck=fck,
        fy=fy,
        exposure=exposure,
        b=b,
        support_width_mm=support_width_mm,
        max_aggregate_size_mm=max_aggregate_size_mm,
    )

    if sizing_res.get("status") == "needs_review":
        return {
            "status": "needs_review",
            "reason": sizing_res.get("reason"),
            "shear_status": sizing_res.get("shear_status", "needs_review"),
            "sizing": sizing_res,
            "validation": None,
        }

    validation_res = validate_design(sizing_res["design_dict"])

    return {
        "status": validation_res["status"],
        "shear_status": sizing_res["shear_status"],
        "sizing": sizing_res,
        "validation": validation_res,
    }
