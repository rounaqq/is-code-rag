"""
Unit tests for IS 456:2000 Slab AutoCAD DXF Drafting Engine.
Verifies file generation, layer structure, geometry, and mandatory draft disclaimer watermark.
"""

from pathlib import Path
import ezdxf
from src.generation.slab_sizing import size_slab_from_loads
from src.cad.slab_dxf import export_slab_dxf, DRAFT_WATERMARK_TEXT


def test_export_slab_dxf_file_created(tmp_path):
    """Generates complete AutoCAD DXF file for a designed RC slab."""
    sizing = size_slab_from_loads(
        lx_m=2.5,
        ly_m=5.0,
        live_load_kN_m2=3.0,
    )
    assert sizing["status"] == "success"

    out_file = tmp_path / "test_slab.dxf"
    res = export_slab_dxf(sizing["design_dict"], output_path=str(out_file))

    assert res["status"] == "success"
    assert out_file.exists()
    assert out_file.stat().st_size > 1000


def test_slab_dxf_layers_and_watermark(tmp_path):
    """Verifies standard AutoCAD layers and presence of the mandatory draft disclaimer watermark."""
    sizing = size_slab_from_loads(
        lx_m=3.0,
        ly_m=3.5,
        live_load_kN_m2=2.5,
    )
    out_file = tmp_path / "test_two_way_slab.dxf"
    export_slab_dxf(sizing["design_dict"], output_path=str(out_file))

    doc = ezdxf.readfile(str(out_file))
    layers = [lay.dxf.name for lay in doc.layers]
    assert "CONCRETE_OUTLINE" in layers
    assert "REBAR_MAIN" in layers
    assert "REBAR_DIST" in layers
    assert "WATERMARK" in layers

    msp = doc.modelspace()
    text_entities = [e.dxf.text for e in msp.query("TEXT")]
    assert any(DRAFT_WATERMARK_TEXT in t for t in text_entities)
