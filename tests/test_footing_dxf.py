"""
Unit tests for IS 456:2000 Isolated Footing AutoCAD DXF Drafting Engine.
Verifies file generation, layer structure, geometry, and mandatory draft disclaimer watermark.
"""

from pathlib import Path
import ezdxf
from src.generation.footing_sizing import size_footing_from_load
from src.cad.footing_dxf import export_footing_dxf, DRAFT_WATERMARK_TEXT


def test_export_footing_dxf_file_created(tmp_path):
    """Generates complete AutoCAD DXF file for a designed isolated RC footing."""
    sizing = size_footing_from_load(
        axial_load_kN=1000.0,
        sbc_kN_m2=200.0,
    )
    assert sizing["status"] == "success"

    out_file = tmp_path / "test_footing.dxf"
    res = export_footing_dxf(sizing["design_dict"], output_path=str(out_file))

    assert res["status"] == "success"
    assert out_file.exists()
    assert out_file.stat().st_size > 1000


def test_footing_dxf_layers_and_watermark(tmp_path):
    """Verifies standard AutoCAD layers and presence of the mandatory draft disclaimer watermark."""
    sizing = size_footing_from_load(
        axial_load_kN=1200.0,
        sbc_kN_m2=220.0,
    )
    out_file = tmp_path / "test_footing_layers.dxf"
    export_footing_dxf(sizing["design_dict"], output_path=str(out_file))

    doc = ezdxf.readfile(str(out_file))
    layers = [lay.dxf.name for lay in doc.layers]
    assert "CONCRETE_OUTLINE" in layers
    assert "COLUMN_OUTLINE" in layers
    assert "REBAR_MAIN" in layers
    assert "WATERMARK" in layers

    msp = doc.modelspace()
    text_entities = [e.dxf.text for e in msp.query("TEXT")]
    assert any(DRAFT_WATERMARK_TEXT in t for t in text_entities)
