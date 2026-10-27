"""
Unit tests for 2D AutoCAD DXF Column Drawing Generation (src/cad/column_dxf.py).
Validates:
  - Standard AutoCAD layer creation (CONCRETE, REBAR, TIES, DIMENSIONS, ANNOTATIONS, TITLE_BLOCK)
  - Entity geometry (boundary polyline, rebar circles, tie links)
  - Mandatory draft status stamp: "STATUS: DRAFT - NOT FOR CONSTRUCTION. Not engineer-reviewed."
"""

from pathlib import Path
import pytest
import ezdxf

from src.generation.column_sizing import size_column_from_load
from src.cad.column_dxf import export_column_dxf


def test_column_dxf_export_and_layers(tmp_path):
    """Generates a column DXF and verifies layer definitions and entities."""
    res = size_column_from_load(axial_load_kN=1000.0, length_m=3.0, fck=25.0, fy=500.0)
    assert res["status"] == "success"

    out_file = tmp_path / "test_column.dxf"
    export_res = export_column_dxf(res["design_dict"], str(out_file))

    assert export_res["status"] == "success"
    assert out_file.exists()

    # Read with ezdxf
    doc = ezdxf.readfile(str(out_file))
    layer_names = [layer.dxf.name for layer in doc.layers]

    for expected_layer in ["CONCRETE", "REBAR", "TIES", "DIMENSIONS", "ANNOTATIONS", "TITLE_BLOCK"]:
        assert expected_layer in layer_names, f"Missing layer {expected_layer}"

    msp = doc.modelspace()
    circles = msp.query("CIRCLE")
    assert len(circles) >= 4, "Must have at least 4 longitudinal rebar circles"

    polylines = msp.query("LWPOLYLINE")
    assert len(polylines) >= 3, "Must have concrete boundary, tie rectangle, and title block"


def test_column_dxf_title_block_draft_stamp(tmp_path):
    """Title block must enforce draft status."""
    res = size_column_from_load(axial_load_kN=1200.0, length_m=3.0, fck=25.0, fy=500.0)
    out_file = tmp_path / "draft_column.dxf"
    export_column_dxf(res["design_dict"], str(out_file))

    doc = ezdxf.readfile(str(out_file))
    texts = [e.dxf.text for e in doc.modelspace().query("TEXT")]

    has_draft_stamp = any("STATUS: DRAFT - NOT FOR CONSTRUCTION" in t for t in texts)
    assert has_draft_stamp, "Must display mandatory DRAFT status in title block"
