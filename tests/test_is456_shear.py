"""
Unit tests for deterministic IS 456:2000 Clause 40 shear design (src/validation/is456_shear.py).
Validates Clause 40.1, 40.2.3, 40.3, 40.4, 40.4(a), Table 19, Table 20,
Cl. 26.5.1.5, and Cl. 26.5.1.6.
Does NOT read .env or make network calls.
"""

import json
from pathlib import Path
import pytest

from src.validation.is456_shear import tau_c_lookup, shear_design


def test_cl40_json_schema_and_verification():
    """Verify data/processed/is456_cl_40.json loads, has verified=true and required items."""
    json_path = Path("data/processed/is456_cl_40.json")
    assert json_path.exists(), f"Missing {json_path}"

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["code_id"] == "IS 456"
    assert data["edition_year"] == 2000
    assert data["clause_reference"] == "40"
    assert data["verified"] is True
    assert "page_085.png" in data["verified_by"]
    assert "page_086.png" in data["verified_by"]

    item_ids = [item["id"] for item in data["items"]]
    assert "40.1" in item_ids
    assert "40.2.3" in item_ids
    assert "40.3" in item_ids
    assert "40.4" in item_ids
    assert "40.4(a)" in item_ids


def test_tau_c_lookup():
    """Verify Table 19 row selection rule, grade mappings, and unsupported fck rejection."""
    # pt below 0.15 uses first row (pt = 0.15)
    assert tau_c_lookup(0.10, 25) == 0.29

    # pt at or above 3.0 uses last row (pt = 3.0)
    assert tau_c_lookup(3.5, 25) == 0.92

    # fck >= 40 uses "M40 and above" column
    assert tau_c_lookup(0.15, 45) == 0.30
    assert tau_c_lookup(0.50, 40) == 0.51

    # fck of 22 is not 15, 20, 25, 30, 35 or >=40 -> raises ValueError
    with pytest.raises(ValueError, match="needs engineer decision"):
        tau_c_lookup(0.50, 22)

    # Invalid pt or fck
    with pytest.raises(ValueError):
        tau_c_lookup(-0.1, 25)
    with pytest.raises(ValueError):
        tau_c_lookup(0.5, -25)


def test_shear_design_vu_150kN_stirrups_designed():
    """
    Hand-check values (b=300, d=450, fck=25, fy_stirrup=500, ast=1256.64, stirrup_dia=8):
    vu=150000:
      tau_v 1.111, pt 0.931, tau_c 0.57, vus 73050, sv_calc 223.6, sv_min_steel 302.5,
      sv_cap 300, spacing 223.6, suggested 220, status 'stirrups_designed' (tolerance 0.1%)
    """
    res = shear_design(
        b=300.0,
        d=450.0,
        fck=25.0,
        fy_stirrup=500.0,
        vu=150000.0,
        ast_provided=1256.64,
        stirrup_dia=8.0,
        legs=2,
    )

    assert res["status"] == "stirrups_designed"
    assert pytest.approx(res["tau_v"], rel=1e-3) == 1.111
    assert pytest.approx(res["pt"], rel=1e-3) == 0.931
    assert res["tau_c"] == 0.57
    assert pytest.approx(res["vus"], rel=1e-3) == 73050.0
    assert pytest.approx(res["sv_calc"], rel=1e-3) == 223.6
    assert pytest.approx(res["sv_min_steel"], rel=1e-3) == 302.5
    assert res["sv_cap"] == 300.0
    assert pytest.approx(res["spacing_mm"], rel=1e-3) == 223.6
    assert res["suggested_spacing_mm"] == 220.0

    # Citations & Notes
    assert "IS 456:2000 Cl. 40.4" in res["citations"]
    assert "IS 456:2000 Cl. 40.4(a)" in res["citations"]
    assert any("continues at least d beyond" in n for n in res["notes"])
    assert any("critical section" in n for n in res["notes"])
    assert any("ASSUMPTION" in n for n in res["notes"])


def test_shear_design_vu_60kN_minimum_shear_steel():
    """
    Hand-check values (b=300, d=450, fck=25, fy_stirrup=500, ast=1256.64, stirrup_dia=8):
    vu=60000: tau_v 0.444, status 'minimum_shear_steel', spacing 300
    """
    res = shear_design(
        b=300.0,
        d=450.0,
        fck=25.0,
        fy_stirrup=500.0,
        vu=60000.0,
        ast_provided=1256.64,
        stirrup_dia=8.0,
        legs=2,
    )

    assert res["status"] == "minimum_shear_steel"
    assert pytest.approx(res["tau_v"], rel=1e-3) == 0.444
    assert res["tau_c"] == 0.57
    assert res["vus"] is None
    assert res["sv_calc"] is None
    assert res["spacing_mm"] == 300.0
    assert res["suggested_spacing_mm"] == 300.0
    assert "IS 456:2000 Cl. 40.3" in res["citations"]


def test_shear_design_vu_500kN_section_too_small():
    """
    Hand-check values (b=300, d=450, fck=25, fy_stirrup=500, ast=1256.64, stirrup_dia=8):
    vu=500000: status 'section_too_small'
    """
    res = shear_design(
        b=300.0,
        d=450.0,
        fck=25.0,
        fy_stirrup=500.0,
        vu=500000.0,
        ast_provided=1256.64,
        stirrup_dia=8.0,
        legs=2,
    )

    assert res["status"] == "section_too_small"
    assert res["tau_v"] > res["tau_c_max"]
    assert res["spacing_mm"] is None
    assert res["suggested_spacing_mm"] is None
    assert "IS 456:2000 Cl. 40.2.3" in res["citations"]


def test_fy_stirrup_cap_at_415():
    """fy_stirrup=500 gives the exact same result as fy_stirrup=415 per Cl. 40.4(a)."""
    r500 = shear_design(
        b=300.0,
        d=450.0,
        fck=25.0,
        fy_stirrup=500.0,
        vu=150000.0,
        ast_provided=1256.64,
        stirrup_dia=8.0,
        legs=2,
    )
    r415 = shear_design(
        b=300.0,
        d=450.0,
        fck=25.0,
        fy_stirrup=415.0,
        vu=150000.0,
        ast_provided=1256.64,
        stirrup_dia=8.0,
        legs=2,
    )

    assert r500["spacing_mm"] == r415["spacing_mm"]
    assert r500["suggested_spacing_mm"] == r415["suggested_spacing_mm"]
    assert r500["sv_calc"] == r415["sv_calc"]
    assert r500["sv_min_steel"] == r415["sv_min_steel"]


def test_invalid_and_zero_inputs():
    """b=0 and other zero/negative inputs raise ValueError."""
    with pytest.raises(ValueError, match="strictly positive"):
        shear_design(b=0, d=450, fck=25, fy_stirrup=500, vu=150000, ast_provided=1256.64, stirrup_dia=8)

    with pytest.raises(ValueError, match="strictly positive"):
        shear_design(b=300, d=-450, fck=25, fy_stirrup=500, vu=150000, ast_provided=1256.64, stirrup_dia=8)

    with pytest.raises(ValueError, match="strictly positive"):
        shear_design(b=300, d=450, fck=25, fy_stirrup=500, vu=-150000, ast_provided=1256.64, stirrup_dia=8)

    with pytest.raises(ValueError, match="strictly positive"):
        shear_design(b=300, d=450, fck=25, fy_stirrup=500, vu=150000, ast_provided=0, stirrup_dia=8)


def test_spacing_below_100mm_needs_review():
    """If spacing is below 100 mm, status is set to needs_review."""
    # High shear close to tau_c_max, small stirrup dia 6mm
    res = shear_design(
        b=230.0,
        d=300.0,
        fck=20.0,
        fy_stirrup=415.0,
        vu=170000.0,  # tau_v = 170000 / 69000 = 2.46 (tau_c_max for M20 is 2.8)
        ast_provided=500.0,
        stirrup_dia=6.0,
        legs=2,
    )
    assert res["status"] == "needs_review"
    assert res["spacing_mm"] < 100.0
    assert any("below 100 mm" in n for n in res["notes"])
