"""
Unit tests for IS 456:2000 Column Sizing Engine (src/generation/column_sizing.py).
Validates:
  - Clause 25.1.2: Slenderness limits (short vs slender)
  - Clause 25.4: Minimum eccentricity (emin <= 0.05D)
  - Clause 39.3: Axial load capacity formula
  - Clause 26.5.3.1: Minimum (0.8%) and maximum (4.0%) longitudinal steel
  - Clause 26.5.3.1: Minimum bar diameter (12mm) and periphery spacing (<= 300mm)
  - Clause 26.5.3.2: Lateral tie diameter and pitch limits
  - Clause 26.4.2 & Table 16: Nominal cover
"""

import pytest
from src.generation.column_sizing import (
    check_slenderness,
    check_minimum_eccentricity,
    calculate_required_steel,
    select_column_rebar,
    design_lateral_ties,
    size_column_from_load,
)


def test_slenderness_short_column():
    """3.0m column with 400x400mm section is short (ratio 7.5 < 12)."""
    res = check_slenderness(length_m=3.0, b_mm=400.0, D_mm=400.0)
    assert res["is_short"] is True
    assert res["lambda_D"] == 7.5
    assert res["lambda_b"] == 7.5


def test_slenderness_slender_column():
    """6.0m column with 300x300mm section is slender (ratio 20.0 >= 12)."""
    res = check_slenderness(length_m=6.0, b_mm=300.0, D_mm=300.0)
    assert res["is_short"] is False
    assert res["lambda_D"] == 20.0


def test_minimum_eccentricity_valid():
    """3.0m column with 400mm dimension satisfies emin <= 0.05*D (20mm <= 20mm)."""
    res = check_minimum_eccentricity(length_m=3.0, b_mm=400.0, D_mm=400.0)
    assert res["axial_formula_valid"] is True
    assert res["emin_D_mm"] == 20.0
    assert res["limit_D_mm"] == 20.0


def test_minimum_eccentricity_exceeds_limit():
    """3.0m column with 300mm dimension has emin=20mm > 0.05*300=15mm, requires bending design."""
    res = check_minimum_eccentricity(length_m=3.0, b_mm=300.0, D_mm=300.0)
    assert res["axial_formula_valid"] is False
    assert res["emin_D_mm"] == 20.0
    assert res["limit_D_mm"] == 15.0


def test_steel_calculation_enforces_0_8_percent_floor():
    """When concrete alone can support the load, minimum 0.8% steel is enforced."""
    # 400x400 mm, M25, Fe500, light load 500 kN
    res = calculate_required_steel(Pu_kN=500.0, b_mm=400.0, D_mm=400.0, fck=25.0, fy=500.0)
    assert res["raw_Asc_req_mm2"] < 0  # concrete alone is enough
    assert res["Asc_min_mm2"] == 1280.0  # 0.8% of 160,000
    assert res["governing_Asc_req_mm2"] == 1280.0
    assert res["pt_req_pct"] == 0.80
    assert res["exceeds_max_steel"] is False


def test_steel_calculation_heavily_loaded():
    """Heavily loaded column computes steel per Cl. 39.3."""
    # 400x400 mm, M25, Fe500, Pu = 2000 kN
    # Pu = 0.4*25*160000 + (0.67*500 - 0.4*25)*Asc = 1600000 + (335 - 10)*Asc = 1600000 + 325*Asc
    # Asc = (2000000 - 1600000) / 325 = 400000 / 325 = 1230.77 mm2 < 1280 (min governs)
    # Pu = 2500 kN -> Asc = (2500000 - 1600000) / 325 = 900000 / 325 = 2769.2 mm2
    res = calculate_required_steel(Pu_kN=2500.0, b_mm=400.0, D_mm=400.0, fck=25.0, fy=500.0)
    assert round(res["governing_Asc_req_mm2"], 1) == 2769.2
    assert res["exceeds_max_steel"] is False


def test_steel_calculation_exceeds_4_percent():
    """Extreme load on small column exceeds 4.0% steel ceiling."""
    res = calculate_required_steel(Pu_kN=5000.0, b_mm=400.0, D_mm=400.0, fck=25.0, fy=500.0)
    assert res["exceeds_max_steel"] is True


def test_select_column_rebar_rules():
    """Bar arrangement satisfies count >= 4, dia >= 12mm, periphery <= 300mm, and clear gap >= 25mm."""
    # Require 1280 mm2 steel on 400x400 mm
    rebar = select_column_rebar(Asc_req_mm2=1280.0, b_mm=400.0, D_mm=400.0, cover_mm=40.0)
    assert rebar is not None
    assert rebar["bar_count"] in [4, 6, 8]
    assert rebar["bar_diameter_mm"] >= 12
    assert rebar["area_provided_mm2"] >= 1280.0
    assert rebar["max_spacing_mm"] <= 300.0
    assert rebar["clear_spacing_mm"] >= 25.0


def test_design_lateral_ties_specifications():
    """Tie diameter >= max(phi/4, 6mm) and pitch <= min(b, 16*phi, 300mm)."""
    # Main bar 16mm on 400x400 mm
    ties = design_lateral_ties(main_bar_dia_mm=16.0, b_mm=400.0, D_mm=400.0)
    assert ties["tie_diameter_mm"] == 8
    # pitch <= min(400, 16*16=256, 300) = 256 -> rounded down to 250 mm
    assert ties["tie_pitch_mm"] == 250
    assert ties["callout"] == "T8 @ 250 c/c"


def test_size_column_from_load_end_to_end_success():
    """Full end-to-end auto-sizing of 1000 kN column."""
    res = size_column_from_load(axial_load_kN=1000.0, length_m=3.0, fck=25.0, fy=500.0)
    assert res["status"] == "success"
    design = res["design_dict"]
    assert design["member_type"] == "column"
    assert design["status"] == "PASSED"
    assert design["approval_status"] == "STATUS: DRAFT - NOT FOR CONSTRUCTION. Not engineer-reviewed."
    assert design["cover_mm"] == 40
    assert design["rebar_selected"]["area_provided_mm2"] >= design["steel_required_mm2"]
    assert design["axial_capacity_Pu_kN"] >= design["factored_axial_load_Pu_kN"]
    assert len(design["citations"]) >= 5


def test_size_column_slenderness_rejection():
    """Slender column specified by user is rejected with needs_review."""
    res = size_column_from_load(axial_load_kN=800.0, length_m=5.0, b_mm=300.0, D_mm=300.0)
    assert res["status"] == "needs_review"
    assert "slender" in res["reason"].lower() or "eccentricity" in res["reason"].lower()
