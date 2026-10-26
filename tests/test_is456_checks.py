"""
Unit tests for IS 456:2000 deterministic structural checks (src/validation/is456_checks.py).
Validates hand-calculated limits, pass/fail conditions, citations, and error boundaries.
"""

import math
import pytest
from src.validation.is456_checks import (
    min_tension_steel,
    max_tension_steel,
    max_compression_steel,
    max_stirrup_spacing,
    min_shear_steel,
    max_torsion_stirrup_spacing,
    nominal_cover,
    shear_strength_tau_c,
    unit_weight_concrete,
    effective_span_simply_supported,
    design_bond_stress,
    development_length,
    deflection_check,
    min_bar_clear_spacing,
)



def test_min_tension_steel():
    # Hand-calculated case: b=300, d=450, fy=500: min steel required = 229.5 mm2
    res_pass = min_tension_steel(b=300, d=450, fy=500, ast_provided=250.0)
    assert res_pass["required"] == 229.5
    assert res_pass["passed"] is True
    assert res_pass["citation"] == "IS 456:2000 Cl. 26.5.1.1(a)"
    assert "A_s" in res_pass["formula"]

    # Fail case
    res_fail = min_tension_steel(b=300, d=450, fy=500, ast_provided=200.0)
    assert res_fail["required"] == 229.5
    assert res_fail["passed"] is False

    # Zero or negative dimensions rejected
    with pytest.raises(ValueError):
        min_tension_steel(b=0, d=450, fy=500, ast_provided=250)
    with pytest.raises(ValueError):
        min_tension_steel(b=300, d=-450, fy=500, ast_provided=250)
    with pytest.raises(ValueError):
        min_tension_steel(b=300, d=450, fy=0, ast_provided=250)


def test_max_tension_steel():
    # Hand-calculated case: b=300, D=500: max tension steel = 6000 mm2
    res_pass = max_tension_steel(b=300, D=500, ast_provided=5500.0)
    assert res_pass["required"] == 6000.0
    assert res_pass["passed"] is True
    assert res_pass["citation"] == "IS 456:2000 Cl. 26.5.1.1(b)"

    # Fail case
    res_fail = max_tension_steel(b=300, D=500, ast_provided=6500.0)
    assert res_fail["required"] == 6000.0
    assert res_fail["passed"] is False

    # Zero or negative dimensions rejected
    with pytest.raises(ValueError):
        max_tension_steel(b=-300, D=500, ast_provided=1000)
    with pytest.raises(ValueError):
        max_tension_steel(b=300, D=0, ast_provided=1000)


def test_max_compression_steel():
    # Pass case
    res_pass = max_compression_steel(b=300, D=500, asc_provided=4000.0)
    assert res_pass["required"] == 6000.0
    assert res_pass["passed"] is True
    assert res_pass["citation"] == "IS 456:2000 Cl. 26.5.1.2"

    # Fail case
    res_fail = max_compression_steel(b=300, D=500, asc_provided=6500.0)
    assert res_fail["required"] == 6000.0
    assert res_fail["passed"] is False

    # Zero or negative dimensions rejected
    with pytest.raises(ValueError):
        max_compression_steel(b=0, D=500, asc_provided=1000)


def test_max_stirrup_spacing():
    # Hand-calculated case: d=450 vertical: limit = 300 (0.75d = 337.5, capped at 300)
    res_vert_pass = max_stirrup_spacing(d=450, spacing=250, inclined_45=False)
    assert res_vert_pass["required"] == 300.0
    assert res_vert_pass["passed"] is True
    assert res_vert_pass["citation"] == "IS 456:2000 Cl. 26.5.1.5"

    # Fail case (vertical)
    res_vert_fail = max_stirrup_spacing(d=450, spacing=320, inclined_45=False)
    assert res_vert_fail["required"] == 300.0
    assert res_vert_fail["passed"] is False

    # Inclined 45°: limit is min(d, 300) -> d=250 gives limit 250
    res_inc_pass = max_stirrup_spacing(d=250, spacing=240, inclined_45=True)
    assert res_inc_pass["required"] == 250.0
    assert res_inc_pass["passed"] is True

    # Fail case (inclined)
    res_inc_fail = max_stirrup_spacing(d=250, spacing=260, inclined_45=True)
    assert res_inc_fail["required"] == 250.0
    assert res_inc_fail["passed"] is False

    # Zero or negative dimensions rejected
    with pytest.raises(ValueError):
        max_stirrup_spacing(d=0, spacing=100)
    with pytest.raises(ValueError):
        max_stirrup_spacing(d=450, spacing=-50)


def test_min_shear_steel():
    # Hand-calculated case: fy=500 treated as 415, b=300, sv=150: min Asv approx 49.85 mm2
    res_pass = min_shear_steel(b=300, sv=150, fy=500, asv_provided=55.0)
    assert math.isclose(res_pass["required"], 49.8546, rel_tol=1e-3)
    assert res_pass["passed"] is True
    assert res_pass["citation"] == "IS 456:2000 Cl. 26.5.1.6"

    # Fail case
    res_fail = min_shear_steel(b=300, sv=150, fy=500, asv_provided=40.0)
    assert math.isclose(res_fail["required"], 49.8546, rel_tol=1e-3)
    assert res_fail["passed"] is False

    # Zero or negative dimensions rejected
    with pytest.raises(ValueError):
        min_shear_steel(b=0, sv=150, fy=500, asv_provided=50)
    with pytest.raises(ValueError):
        min_shear_steel(b=300, sv=0, fy=500, asv_provided=50)


def test_max_torsion_stirrup_spacing():
    # x1=200, y1=400: least of 200, (200+400)/4 = 150, 300 -> limit is 150
    res_pass = max_torsion_stirrup_spacing(x1=200, y1=400, spacing=140)
    assert res_pass["required"] == 150.0
    assert res_pass["passed"] is True
    assert res_pass["citation"] == "IS 456:2000 Cl. 26.5.1.7(a)"

    # Fail case
    res_fail = max_torsion_stirrup_spacing(x1=200, y1=400, spacing=160)
    assert res_fail["required"] == 150.0
    assert res_fail["passed"] is False

    # Zero or negative dimensions rejected
    with pytest.raises(ValueError):
        max_torsion_stirrup_spacing(x1=-10, y1=400, spacing=100)


def test_nominal_cover():
    # Hand-calculated cases: cover Moderate = 30, Severe = 45
    res_mod = nominal_cover("Moderate")
    assert res_mod["required"] == 30
    assert res_mod["citation"] == "IS 456:2000 Table 16"
    assert res_mod == 30

    res_sev = nominal_cover("Severe")
    assert res_sev["required"] == 45
    assert res_sev == 45

    # Pass case with cover_provided
    res_pass = nominal_cover("Moderate", cover_provided=30)
    assert res_pass["passed"] is True

    # Fail case with cover_provided
    res_fail = nominal_cover("Moderate", cover_provided=25)
    assert res_fail["passed"] is False

    # Unknown exposure raises ValueError
    with pytest.raises(ValueError):
        nominal_cover("Tropical")


def test_shear_strength_tau_c():
    # Hand-calculated case: tau_c for pt=1.00, M25 = 0.64
    res_exact = shear_strength_tau_c(pt=1.00, grade="M25")
    assert res_exact["required"] == 0.64
    assert res_exact["tau_c"] == 0.64
    assert res_exact["citation"] == "IS 456:2000 Table 19"
    assert res_exact == 0.64

    # Pass case with tau_provided
    res_pass = shear_strength_tau_c(pt=1.00, grade="M25", tau_provided=0.50)
    assert res_pass["passed"] is True

    # Fail case with tau_provided
    res_fail = shear_strength_tau_c(pt=1.00, grade="M25", tau_provided=0.75)
    assert res_fail["passed"] is False

    # Hand-calculated requirement: pt=0.60 raises ValueError("needs engineer decision")
    with pytest.raises(ValueError, match="needs engineer decision"):
        shear_strength_tau_c(pt=0.60, grade="M25")

    # Unlisted grade raises ValueError("needs engineer decision")
    with pytest.raises(ValueError, match="needs engineer decision"):
        shear_strength_tau_c(pt=1.00, grade="M10")


def test_unit_weight_concrete():
    """Unit weight per IS 456:2000 Cl. 19.2.1."""
    assert unit_weight_concrete("reinforced") == 25.0
    assert unit_weight_concrete("rcc") == 25.0
    assert unit_weight_concrete("plain") == 24.0
    assert unit_weight_concrete("pcc") == 24.0


def test_effective_span_simply_supported():
    """Effective span for simply supported beam per IS 456:2000 Cl. 22.2(a)."""
    # clear_span=5000, d=400, support_width=300:
    # clear + d = 5400, clear + support = 5300 -> min is 5300
    res = effective_span_simply_supported(clear_span_mm=5000.0, d_mm=400.0, support_width_mm=300.0)
    assert res["effective_span_mm"] == 5300.0
    assert res["effective_span_m"] == 5.3
    assert res["governing_criterion"] == "clear_span + support_width"
    assert res["citation"] == "IS 456:2000 Cl. 22.2(a)"

    # Governing by clear_span + d when support is wider
    res2 = effective_span_simply_supported(clear_span_mm=5000.0, d_mm=300.0, support_width_mm=450.0)
    assert res2["effective_span_mm"] == 5300.0
    assert res2["governing_criterion"] == "clear_span + d"

    # Zero or negative inputs raise ValueError
    with pytest.raises(ValueError):
        effective_span_simply_supported(clear_span_mm=0, d_mm=300, support_width_mm=300)


def test_design_bond_stress():
    """Design bond stress tau_bd per IS 456:2000 Cl. 26.2.1.1."""
    # Plain bars in tension
    assert design_bond_stress(20, bar_type="plain", stress_type="tension") == 1.2
    assert design_bond_stress(25, bar_type="plain", stress_type="tension") == 1.4
    assert design_bond_stress(30, bar_type="plain", stress_type="tension") == 1.5
    assert design_bond_stress(35, bar_type="plain", stress_type="tension") == 1.7
    assert design_bond_stress(40, bar_type="plain", stress_type="tension") == 1.9

    # Deformed bars: +60%
    # M25 deformed: 1.4 * 1.6 = 2.24
    assert math.isclose(design_bond_stress(25, bar_type="deformed", stress_type="tension"), 2.24, rel_tol=1e-3)

    # Bars in compression: +25%
    # M20 plain compression: 1.2 * 1.25 = 1.5
    assert math.isclose(design_bond_stress(20, bar_type="plain", stress_type="compression"), 1.50, rel_tol=1e-3)

    # Grade below M20 raises ValueError
    with pytest.raises(ValueError, match="needs engineer decision"):
        design_bond_stress(15)


def test_development_length():
    """Development length Ld per IS 456:2000 Cl. 26.2.1 and anchorage per Cl. 26.2.3.3."""
    # Fe 500, M25, 16 mm bar:
    # sigma_s = 0.87 * 500 = 435 N/mm2
    # tau_bd = 1.4 * 1.6 = 2.24 N/mm2
    # Ld = (16 * 435) / (4 * 2.24) = 776.786 mm
    res = development_length(bar_dia_mm=16.0, fck=25.0, fy=500.0, bar_type="deformed")
    assert math.isclose(res["ld_mm"], 776.786, rel_tol=1e-3)
    assert res["ld_rounded_mm"] == 780.0
    assert res["support_anchorage_min_mm"] == 260.0  # ceil(776.786/3/5)*5 = 260
    assert "Cl. 26.2.1" in res["citation"]

    # Zero or negative inputs raise ValueError
    with pytest.raises(ValueError):
        development_length(bar_dia_mm=-16, fck=25, fy=500)


def test_deflection_check():
    """Deflection control span-to-effective-depth ratio per IS 456:2000 Cl. 23.2.1 (indicative)."""
    # Simply supported beam: span = 5.0m, d_actual = 400 mm, fy = 500
    # Ast_req = 500 mm2, Ast_prov = 600 mm2, b = 300 mm
    # Basic ratio = 20.0, actual L/d = 5000 / 400 = 12.5
    res = deflection_check(
        span_m=5.0,
        d_actual_mm=400.0,
        fy=500.0,
        ast_required_mm2=500.0,
        ast_provided_mm2=600.0,
        b_mm=300.0,
        member_type="simply_supported",
    )
    assert res["status"] == "indicative"
    assert res["ratio_satisfied"] is True
    assert "approximate curve fit that is NOT from IS 456" in res["note"]
    assert res["actual_ld_ratio"] == 12.5
    assert res["basic_ratio"] == 20.0
    assert res["modification_factor_f1"] > 1.0
    assert "modification_factor_f1_unclamped" in res
    assert res["actual_ld_ratio"] <= res["max_ld_ratio"]
    assert "Cl. 23.2.1" in res["citation"]

    # Slender beam failing deflection: span = 8.0m, d_actual = 250 mm -> actual L/d = 32
    res_fail = deflection_check(
        span_m=8.0,
        d_actual_mm=250.0,
        fy=500.0,
        ast_required_mm2=1000.0,
        ast_provided_mm2=1000.0,
        b_mm=230.0,
    )
    assert res_fail["status"] == "indicative"
    assert res_fail["ratio_satisfied"] is False
    assert res_fail["actual_ld_ratio"] == 32.0
    assert res_fail["actual_ld_ratio"] > res_fail["max_ld_ratio"]


def test_deflection_check_fs_above_290():
    """fs above 290 N/mm2 sets status needs_review with note Outside the range of Fig. 4."""
    # fy=550, ast_req=1000, ast_prov=1000 -> fs = 0.58 * 550 * 1.0 = 319.0 > 290
    res = deflection_check(
        span_m=5.0,
        d_actual_mm=400.0,
        fy=550.0,
        ast_required_mm2=1000.0,
        ast_provided_mm2=1000.0,
        b_mm=300.0,
    )
    assert res["status"] == "needs_review"
    assert "Outside the range of Fig. 4" in res["note"]
    assert res["passed"] is False


def test_deflection_check_pt_above_3():
    """pt above 3.0 sets status needs_review with note Outside the range of Fig. 4."""
    # b=200, d=200, ast_prov=1500 -> pt = (100 * 1500) / (200 * 200) = 3.75 > 3.0
    res = deflection_check(
        span_m=4.0,
        d_actual_mm=200.0,
        fy=415.0,
        ast_required_mm2=1000.0,
        ast_provided_mm2=1500.0,
        b_mm=200.0,
    )
    assert res["status"] == "needs_review"
    assert "Outside the range of Fig. 4" in res["note"]
    assert res["passed"] is False


def test_deflection_check_fs_below_120():
    """fs below 120 uses fs=120 and notes it, keeping status indicative."""
    # fy=415, ast_req=400, ast_prov=1000 -> fs = 0.58 * 415 * (400/1000) = 96.28 < 120
    res = deflection_check(
        span_m=5.0,
        d_actual_mm=400.0,
        fy=415.0,
        ast_required_mm2=400.0,
        ast_provided_mm2=1000.0,
        b_mm=300.0,
    )
    assert res["status"] == "indicative"
    assert res["service_stress_fs"] == 96.28
    assert res["service_stress_fs_used"] == 120.0
    assert "120" in res["note"]
    assert "approximate curve fit that is NOT from IS 456" in res["note"]
    assert res["modification_factor_f1"] > 0
    assert res["modification_factor_f1"] <= 2.0



def test_min_bar_clear_spacing():
    """Minimum horizontal distance between individual parallel bars per IS 456:2000 Cl. 26.3.2(a)."""
    # 4 bars of 16 mm in beam b=230, cover=20, stirrup=8, agg=20 mm:
    # clear_gap = (230 - 40 - 16 - 64) / 3 = 110 / 3 = 36.67 mm >= max(16, 25) = 25 mm -> Pass
    res_pass = min_bar_clear_spacing(
        b=230.0,
        cover_mm=20.0,
        stirrup_dia=8.0,
        n_bars=4,
        bar_dia=16.0,
        max_aggregate_size_mm=20.0,
    )
    assert res_pass["passed"] is True
    assert res_pass["provided"] == 36.67
    assert res_pass["required"] == 25.0
    assert res_pass["citation"] == "IS 456:2000 Cl. 26.3.2(a)"

    # 6 bars of 12 mm in beam b=230, cover=20, stirrup=8, agg=20 mm:
    # clear_gap = (230 - 40 - 16 - 72) / 5 = 102 / 5 = 20.4 mm < 25 mm -> Fail
    res_fail = min_bar_clear_spacing(
        b=230.0,
        cover_mm=20.0,
        stirrup_dia=8.0,
        n_bars=6,
        bar_dia=12.0,
        max_aggregate_size_mm=20.0,
    )
    assert res_fail["passed"] is False
    assert res_fail["provided"] == 20.4
    assert res_fail["required"] == 25.0

    # Large bar diameter governing over aggregate size: 32 mm bar -> required = max(32, 25) = 32 mm
    res_large_bar = min_bar_clear_spacing(
        b=300.0,
        cover_mm=30.0,
        stirrup_dia=8.0,
        n_bars=3,
        bar_dia=32.0,
        max_aggregate_size_mm=20.0,
    )
    assert res_large_bar["required"] == 32.0

    # Custom aggregate size (10 mm) -> required = max(12, 15) = 15 mm
    res_custom_agg = min_bar_clear_spacing(
        b=230.0,
        cover_mm=20.0,
        stirrup_dia=8.0,
        n_bars=6,
        bar_dia=12.0,
        max_aggregate_size_mm=10.0,
    )
    assert res_custom_agg["required"] == 15.0
    assert res_custom_agg["passed"] is True

    # Error boundaries: n_bars < 2
    with pytest.raises(ValueError):
        min_bar_clear_spacing(b=230, cover_mm=20, stirrup_dia=8, n_bars=1, bar_dia=16)

    # Error boundaries: negative dimensions
    with pytest.raises(ValueError):
        min_bar_clear_spacing(b=-230, cover_mm=20, stirrup_dia=8, n_bars=4, bar_dia=16)

