"""
Unit tests for IS 800:2007 Structural Steel AutoCAD DXF Drafting Engine.
Verifies file generation, layer structure, geometry layout, and the mandatory
draft disclaimer watermark for both the gusset-plate connection detail and the
truss elevation. Geometry only: no IS 800 capacity claim is made by these drawings.
"""

import ezdxf
from src.cad.steel_dxf import (
    export_steel_connection_dxf,
    export_truss_elevation_dxf,
    DRAFT_WATERMARK_TEXT,
)


def test_export_steel_connection_dxf_file_created(tmp_path):
    """Generates a complete AutoCAD DXF file for a gusset plate bolted connection."""
    out_file = tmp_path / "test_steel_connection.dxf"
    res = export_steel_connection_dxf(
        {"plate_width_mm": 250, "plate_height_mm": 300, "bolt_dia_mm": 20},
        output_path=str(out_file),
    )

    assert res["status"] == "success"
    assert res["detail_type"] == "gusset_plate_connection"
    assert out_file.exists()
    assert out_file.stat().st_size > 1000


def test_steel_connection_layers_geometry_and_watermark(tmp_path):
    """Verifies layers, bolt group geometry, and the mandatory draft disclaimer watermark."""
    out_file = tmp_path / "test_steel_connection_layers.dxf"
    export_steel_connection_dxf(
        {
            "plate_width_mm": 250,
            "plate_height_mm": 300,
            "bolt_rows": 2,
            "bolt_cols": 2,
            "weld_type": "fillet",
        },
        output_path=str(out_file),
    )

    doc = ezdxf.readfile(str(out_file))
    layers = [lay.dxf.name for lay in doc.layers]
    for expected in ("STEEL", "BOLTS", "WELDS", "ANNOTATIONS", "TITLE_BLOCK", "WATERMARK"):
        assert expected in layers

    msp = doc.modelspace()
    # 2x2 bolt group => 4 bolt holes on the BOLTS layer
    bolt_circles = [e for e in msp.query("CIRCLE") if e.dxf.layer == "BOLTS"]
    assert len(bolt_circles) == 4

    text_entities = [e.dxf.text for e in msp.query("TEXT")]
    assert any(DRAFT_WATERMARK_TEXT in t for t in text_entities)
    assert any("NO IS 800 CAPACITY CHECK" in t for t in text_entities)


def test_export_truss_elevation_dxf_file_created(tmp_path):
    """Generates a complete AutoCAD DXF file for a truss elevation."""
    out_file = tmp_path / "test_truss_elevation.dxf"
    res = export_truss_elevation_dxf(
        {"span_m": 6.0, "height_m": 1.5, "panels": 4},
        output_path=str(out_file),
    )

    assert res["status"] == "success"
    assert res["detail_type"] == "truss_elevation"
    assert res["panels"] == 4
    assert out_file.exists()
    assert out_file.stat().st_size > 1000


def test_truss_elevation_layers_geometry_and_watermark(tmp_path):
    """Verifies layers, panel-point count, and the mandatory draft disclaimer watermark."""
    out_file = tmp_path / "test_truss_elevation_layers.dxf"
    export_truss_elevation_dxf(
        {"span_m": 6.0, "height_m": 1.5, "panels": 4},
        output_path=str(out_file),
    )

    doc = ezdxf.readfile(str(out_file))
    layers = [lay.dxf.name for lay in doc.layers]
    for expected in ("STEEL", "DIMENSIONS", "ANNOTATIONS", "TITLE_BLOCK", "WATERMARK"):
        assert expected in layers

    msp = doc.modelspace()
    # One panel point circle at each node on both chords: 2 * (panels + 1) = 10
    node_circles = [e for e in msp.query("CIRCLE") if e.dxf.layer == "ANNOTATIONS"]
    assert len(node_circles) == 10

    text_entities = [e.dxf.text for e in msp.query("TEXT")]
    assert any(DRAFT_WATERMARK_TEXT in t for t in text_entities)
    assert any("NO IS 800 CAPACITY CHECK" in t for t in text_entities)
