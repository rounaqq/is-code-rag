"""
Unit tests for IS 456:2000 Isolated Footing Sizing Engine.
Tests plan sizing, punching shear, beam shear, rebar selection, and full auto-sizing.
"""

import pytest
from src.generation.footing_sizing import (
    calculate_footing_plan_dimensions,
    check_two_way_punching_shear,
    check_one_way_beam_shear,
    select_footing_rebar,
    size_footing_from_load,
)


def test_calculate_footing_plan_dimensions():
    """Calculates footing plan dimensions with 10% self-weight allowance."""
    # 1000 kN load, SBC = 200 kN/m2 => A_req = 1.1 * 1000 / 200 = 5.5 m2 => side = 2.345m -> rounded 2.4m
    B, L, actual_pressure, factored_qu = calculate_footing_plan_dimensions(
        axial_load_kN=1000.0,
        sbc_kN_m2=200.0,
        col_b_mm=400.0,
        col_D_mm=400.0,
    )
    assert B == L
    assert B >= 2.3
    assert actual_pressure <= 200.0
    assert factored_qu == round(1.5 * 1000.0 / (B * L), 2)


def test_invalid_load_or_sbc_raises_error():
    """Negative load or SBC raises ValueError in dimension calculator."""
    with pytest.raises(ValueError):
        calculate_footing_plan_dimensions(-500.0, 200.0)
    with pytest.raises(ValueError):
        calculate_footing_plan_dimensions(500.0, -100.0)


def test_check_two_way_punching_shear():
    """Checks two-way punching shear at d/2 from column face."""
    res = check_two_way_punching_shear(
        qu_kN_m2=250.0,
        B_mm=2400.0,
        L_mm=2400.0,
        col_b_mm=400.0,
        col_D_mm=400.0,
        d_mm=450.0,
        fck=25.0,
    )
    # perimeter b0 = 2 * (400 + 450 + 400 + 450) = 3400 mm
    assert res["perimeter_b0_mm"] == 3400.0
    assert res["tau_cp_N_mm2"] == round(0.25 * (25.0**0.5), 3)  # 1.25 N/mm2
    assert res["passed"] is True


def test_check_one_way_beam_shear():
    """Checks one-way shear at d from column face."""
    res = check_one_way_beam_shear(
        qu_kN_m2=250.0,
        B_mm=2400.0,
        cantilever_m=1.0,
        d_mm=450.0,
        fck=25.0,
    )
    assert res["passed"] is True
    assert res["tau_v1_N_mm2"] <= res["tau_c_N_mm2"]


def test_select_footing_rebar():
    """Rebar selection provides >= required steel with spacing <= min(3d, 300mm)."""
    res = select_footing_rebar(
        ast_req=1800.0,
        footing_width_mm=2400.0,
        d_mm=450.0,
    )
    assert res["passed_spacing"] is True
    assert res["ast_provided"] >= res["ast_required"]
    assert res["bar_dia_mm"] >= 12
    assert res["spacing_mm"] <= 300.0


def test_size_footing_from_load_success():
    """End-to-end design of isolated footing (1000 kN, SBC=200) passes all checks."""
    result = size_footing_from_load(
        axial_load_kN=1000.0,
        sbc_kN_m2=200.0,
        col_b_mm=400.0,
        col_D_mm=400.0,
        fck=25.0,
        fy=500.0,
    )
    assert result["status"] == "success"
    assert result["punching_shear_check"] == "PASSED"
    assert result["one_way_shear_check"] == "PASSED"
    assert result["soil_bearing_check"] == "PASSED"
    assert "T" in result["reinforcement_both_ways"]
    assert result["thickness_D_mm"] >= 350.0


def test_size_footing_invalid_inputs_needs_review():
    """Zero or negative loads return needs_review."""
    res = size_footing_from_load(axial_load_kN=-100.0)
    assert res["status"] == "needs_review"
    assert "positive" in res["reason"]
