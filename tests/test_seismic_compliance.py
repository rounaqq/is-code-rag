"""
Unit tests for Step 6 Seismic Compliance & Conflict Resolution Engine.
Validates IS 456 vs IS 13920 governing rule selection in seismic zones.
"""

import pytest
from src.validation.seismic_compliance import (
    resolve_beam_seismic_conflicts,
    resolve_column_seismic_conflicts,
)


def test_beam_seismic_conflict_resolution_zone_iv():
    """Validates that IS 13920 limits govern in Seismic Zone IV."""
    res = resolve_beam_seismic_conflicts(
        b=250.0,
        D=450.0,
        d=400.0,
        fck=25.0,
        fy=415.0,
        ast_provided=1200.0,
        stirrup_dia=8.0,
        stirrup_spacing_midspan=150.0,
        db_min=16.0,
        seismic_zone="IV",
        is_ductile=True,
    )
    assert res["status"] == "COMPLIANT"
    assert res["seismic_active"] is True
    assert len(res["conflicts_resolved"]) >= 3

    # Hinge zone spacing must be <= min(d/4, 8*db_min, 100) = min(100, 128, 100) = 100 mm
    assert res["recommended_hinge_spacing_mm"] <= 100.0
    assert res["hinge_zone_length_mm"] == 800.0  # 2 * d = 2 * 400 = 800 mm

    # Check hook detail is 135 degrees
    hook_check = next(c for c in res["checks"] if c["check"] == "stirrup_hook_detail")
    assert hook_check["hook_angle_deg"] == 135
    assert hook_check["governing_standard"] == "IS 13920:2016 Cl. 5.2"


def test_beam_width_aspect_ratio_non_compliant():
    """Validates that beam narrower than 200 mm or b/D < 0.3 fails IS 13920 Cl. 6.1.1."""
    res = resolve_beam_seismic_conflicts(
        b=180.0,  # Fails < 200 mm
        D=650.0,  # Ratio 180 / 650 = 0.277 < 0.30
        d=600.0,
        fck=25.0,
        fy=415.0,
        ast_provided=1200.0,
        stirrup_dia=8.0,
        stirrup_spacing_midspan=150.0,
        db_min=16.0,
        seismic_zone="V",
        is_ductile=True,
    )
    assert res["status"] == "NON_COMPLIANT"
    width_check = next(c for c in res["checks"] if c["check"] == "beam_width")
    assert width_check["passed"] is False


def test_beam_max_steel_governing_is13920():
    """Validates that IS 13920 caps tension steel at 2.5%, catching over-reinforced designs allowed by IS 456 (4%)."""
    # 3.0% steel: passes IS 456 (<= 4%), fails IS 13920 (<= 2.5%)
    b = 300.0
    d = 500.0
    ast_3_percent = 0.03 * b * d  # 4500 mm2
    res = resolve_beam_seismic_conflicts(
        b=b,
        D=550.0,
        d=d,
        fck=30.0,
        fy=500.0,
        ast_provided=ast_3_percent,
        stirrup_dia=8.0,
        stirrup_spacing_midspan=150.0,
        db_min=25.0,
        seismic_zone="IV",
        is_ductile=True,
    )
    assert res["status"] == "NON_COMPLIANT"
    max_check = next(c for c in res["checks"] if c["check"] == "max_tension_steel_pt")
    assert max_check["passed"] is False
    assert max_check["governing_standard"] == "IS 13920:2016 Cl. 6.2.2"


def test_column_confining_zone_and_tie_pitch():
    """Validates IS 13920 Cl. 7.6.1 confining zone length lo and maximum tie pitch."""
    res = resolve_column_seismic_conflicts(
        b=400.0,
        D=400.0,
        clear_height=3000.0,
        fck=30.0,
        fy=500.0,
        db_min=16.0,
        tie_dia=8.0,
        seismic_zone="IV",
        is_ductile=True,
    )
    assert res["status"] == "COMPLIANT"
    # lo = max(400, 3000/6=500, 450) = 500 mm
    assert res["confining_zone_length_lo_mm"] == 500.0
    # pitch = min(400/4=100, 6*16=96, 100) = 96 mm
    assert res["recommended_confining_pitch_mm"] == 96.0

    tie_check = next(c for c in res["checks"] if c["check"] == "tie_hook_detail")
    assert tie_check["hook_angle_deg"] == 135
    assert tie_check["governing_standard"] == "IS 13920:2016 Cl. 5.2"
