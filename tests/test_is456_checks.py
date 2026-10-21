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
