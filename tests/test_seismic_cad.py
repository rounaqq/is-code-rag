"""
Unit tests for IS 13920 Seismic 2D CAD Blueprint Drafting.
Validates:
  1. Beam 2d plastic hinge confinement stirrup spacing (<= 100 mm) vs midspan spacing.
  2. Beam 135-degree seismic hook detailing on cross-sections.
  3. Column lo confinement zone tie placement and dimensioning.
"""

from pathlib import Path
import pytest
import ezdxf

from src.cad.beam_dxf import (
    compute_seismic_stirrup_positions,
    generate_beam_dxf,
    export_dxf_from_design,
)
from src.cad.column_dxf import export_column_dxf


def test_compute_seismic_stirrup_positions():
    """Validates IS 13920 Cl. 6.3.3: 2d confinement zone has spacing <= 100 mm."""
    span_mm = 5000.0
    support_width_mm = 300.0
    d = 450.0  # 2d = 900 mm
    s_conf = 100.0
    s_mid = 150.0

    positions, left_conf_end, right_conf_start = compute_seismic_stirrup_positions(
        span_mm=span_mm,
        support_width_mm=support_width_mm,
        d=d,
        s_conf=s_conf,
        s_mid=s_mid,
        ox=0.0,
    )

    # Left face is at 300 mm. First stirrup at 350 mm.
    assert positions[0] == 350.0

    # In confinement zone (300 mm to 1200 mm): spacing should be exactly 100 mm
    for i in range(1, 9):
        assert abs((positions[i] - positions[i - 1]) - 100.0) < 1.0

    # Total positions should cover clear span
    assert len(positions) > 20
    assert positions[-1] == (300.0 + 5000.0 - 50.0)  # 5250 mm


def test_generate_seismic_beam_dxf(tmp_path):
    """Validates that beam DXF includes IS 13920 seismic confinement and 135 hook annotations."""
    out_file = tmp_path / "seismic_beam_test.dxf"
    design = {
        "b": 250.0,
        "D": 500.0,
        "d": 450.0,
        "span_m": 5.0,
        "cover_mm": 30.0,
        "main_bar_dia_mm": 16.0,
        "main_bar_count": 3,
        "compression_bar_dia_mm": 12.0,
        "compression_bar_count": 2,
        "stirrup_dia_mm": 8.0,
        "stirrup_spacing_mm": 150.0,
        "fck": 25.0,
        "fy": 500.0,
        "is_seismic": True,
        "seismic_zone": "IV",
    }

    doc = generate_beam_dxf(design, output_path=str(out_file))
    assert out_file.exists()

    # Re-open and verify DXF entities
    read_doc = ezdxf.readfile(str(out_file))
    msp = read_doc.modelspace()
    text_contents = [e.dxf.text for e in msp.query("TEXT")]

    # Check for IS 13920 text annotations
    assert any("IS 13920" in t for t in text_contents)
    assert any("135° Seismic Hook" in t for t in text_contents)


def test_export_seismic_column_dxf(tmp_path):
    """Validates that column DXF includes IS 13920 lo confinement ties and dimensions."""
    out_file = tmp_path / "seismic_col_test.dxf"
    design = {
        "width_mm": 400.0,
        "depth_mm": 400.0,
        "length_m": 3.0,
        "cover_mm": 40.0,
        "fck": 30.0,
        "fy": 500.0,
        "rebar_selected": {
            "bar_count": 8,
            "bar_diameter_mm": 16.0,
            "callout": "8-T16",
        },
        "lateral_ties": {
            "tie_diameter_mm": 8.0,
            "tie_pitch_mm": 250.0,
        },
        "is_seismic": True,
        "seismic_zone": "IV",
    }

    res = export_column_dxf(design, output_path=str(out_file))
    assert res["status"] == "success"
    assert out_file.exists()

    read_doc = ezdxf.readfile(str(out_file))
    msp = read_doc.modelspace()
    text_contents = [e.dxf.text for e in msp.query("TEXT")]

    # lo dimension should be present (lo = max(400, 3000/6=500, 450) = 500 mm)
    assert any("lo = 500 mm" in t for t in text_contents)
    assert any("IS 13920" in t for t in text_contents)
