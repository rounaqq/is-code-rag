"""
Unit tests for IS 456:2000 Slab Sizing Engine.
Tests classification, depth calculation, rebar selection, spacing limits, and full end-to-end sizing.
"""

import pytest
from src.generation.slab_sizing import (
    classify_slab,
    get_table_27_coefficients,
    calculate_slab_depth,
    get_slab_shear_k_factor,
    select_slab_rebar,
    size_slab_from_loads,
)


def test_classify_slab_one_way():
    """Aspect ratio > 2.0 is classified as one-way slab."""
    stype, lx, ly = classify_slab(2.5, 6.0)
    assert stype == "one_way"
    assert lx == 2.5
    assert ly == 6.0


def test_classify_slab_two_way():
    """Aspect ratio <= 2.0 is classified as two-way slab."""
    stype, lx, ly = classify_slab(3.5, 4.2)
    assert stype == "two_way"
    assert lx == 3.5
    assert ly == 4.2


def test_negative_or_zero_spans_raises_error():
    """Zero or negative span lengths raise ValueError."""
    with pytest.raises(ValueError):
        classify_slab(-2.0, 4.0)
    with pytest.raises(ValueError):
        classify_slab(3.0, 0.0)


def test_table_27_coefficients():
    """Interpolates Table 27 bending moment coefficients accurately."""
    ax, ay = get_table_27_coefficients(1.0)
    assert ax == 0.062
    assert ay == 0.062

    ax15, ay15 = get_table_27_coefficients(1.5)
    assert ax15 == 0.104
    assert ay15 == 0.046


def test_calculate_slab_depth():
    """Calculates practical slab depth >= 100 mm with valid cover."""
    d, D = calculate_slab_depth(3.0, support_condition="simply_supported", fy=500.0)
    assert D >= 100.0
    assert d < D
    assert D % 10.0 == 0.0  # rounded to practical multiple of 10 mm


def test_slab_shear_k_factor():
    """Depth factor k is 1.30 for D <= 150mm and 1.00 for D >= 300mm per Cl. 40.2.1.1."""
    assert get_slab_shear_k_factor(125.0) == 1.30
    assert get_slab_shear_k_factor(150.0) == 1.30
    assert get_slab_shear_k_factor(300.0) == 1.00
    assert 1.00 < get_slab_shear_k_factor(225.0) < 1.30


def test_select_slab_rebar_main():
    """Main rebar respects maximum spacing min(3d, 300mm) and maximum diameter D/8."""
    d = 100.0
    D = 125.0
    res = select_slab_rebar(ast_req=350.0, d_mm=d, D_mm=D, is_main_reinforcement=True)
    assert res["meets_max_spacing"] is True
    assert res["meets_max_diameter"] is True
    assert res["spacing_mm"] <= min(3.0 * d, 300.0)
    assert res["bar_dia_mm"] <= D / 8.0
    assert res["ast_provided"] >= res["ast_required"]


def test_select_slab_rebar_distribution():
    """Distribution rebar respects maximum spacing min(5d, 450mm) and maximum diameter D/8."""
    d = 90.0
    D = 125.0
    res = select_slab_rebar(ast_req=150.0, d_mm=d, D_mm=D, is_main_reinforcement=False)
    assert res["meets_max_spacing"] is True
    assert res["meets_max_diameter"] is True
    assert res["spacing_mm"] <= min(5.0 * d, 450.0)


def test_size_slab_from_loads_one_way():
    """End-to-end design of one-way slab (2.5m x 6.0m) passes all structural checks."""
    result = size_slab_from_loads(
        lx_m=2.5,
        ly_m=6.0,
        live_load_kN_m2=3.0,
        floor_finish_kN_m2=1.0,
        fck=25.0,
        fy=500.0,
    )
    assert result["status"] == "success"
    assert result["slab_type"] == "one_way"
    assert result["deflection_check"] == "PASSED"
    assert result["shear_check"] == "PASSED"
    assert "T" in result["main_reinforcement"]
    assert "T" in result["transverse_reinforcement"]

    design = result["design_dict"]
    assert design["checks"]["deflection"]["passed"] is True
    assert design["checks"]["shear"]["passed"] is True
    assert design["checks"]["bar_diameter_limit"]["passed"] is True
    assert design["checks"]["bar_spacing_limit"]["passed"] is True


def test_size_slab_from_loads_two_way():
    """End-to-end design of two-way slab (3.5m x 4.2m) passes all structural checks."""
    result = size_slab_from_loads(
        lx_m=3.5,
        ly_m=4.2,
        live_load_kN_m2=2.5,
        floor_finish_kN_m2=1.0,
        fck=25.0,
        fy=500.0,
    )
    assert result["status"] == "success"
    assert result["slab_type"] == "two_way"
    assert result["deflection_check"] == "PASSED"
    assert result["shear_check"] == "PASSED"

    trans = result["design_dict"]["flexure"]["transverse_reinforcement"]
    assert trans["type"] == "two_way_main_rebar_y"
    assert trans["Mu_y_kNm"] > 0.0


def test_invalid_load_returns_needs_review():
    """Negative live load returns needs_review with explanation."""
    result = size_slab_from_loads(
        lx_m=3.0,
        ly_m=4.0,
        live_load_kN_m2=-5.0,
    )
    assert result["status"] == "needs_review"
    assert "greater than zero" in result["reason"]
