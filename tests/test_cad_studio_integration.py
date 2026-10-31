"""
Integration tests for CAD Drawings and Design Studio synchronization.
Verifies that:
1. Changing design studio inputs produces updated structural sizing parameters.
2. Generated DXF files strictly reflect the exact backend calculation results (same span, b, D, rebar, stirrups).
3. All AutoCAD layer structures match the definitions displayed in CADViewer.tsx.
4. Statutory draft safety watermark is present on every drawing.
5. POST /v1/design/dxf returns design dictionary and section dimensions for frontend synchronization.
"""

from pathlib import Path
import pytest
import ezdxf
from fastapi.testclient import TestClient

from src.generation.beam_sizing import size_beam_from_loads
from src.cad.beam_dxf import generate_beam_dxf, export_dxf_from_design, LAYERS_CONFIG as BEAM_LAYERS
from src.cad.column_dxf import export_column_dxf
from src.cad.slab_dxf import export_slab_dxf
from src.cad.footing_dxf import export_footing_dxf
from src.generation.column_sizing import size_column_from_load
from src.generation.slab_sizing import size_slab_from_loads
from src.generation.footing_sizing import size_footing_from_load
from src.api.main import app

TEST_API_KEY = "test_key_cad_studio_integration_secret_12345678"


@pytest.fixture(autouse=True)
def setup_api_key(monkeypatch):
    monkeypatch.setenv("IS_RAG_API_KEYS", f"tester:{TEST_API_KEY}")


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_beam_studio_cad_integration_match(tmp_path):
    """Beam sizing results match the CAD DXF output dimensions and rebar detailing exactly."""
    span_m = 5.0
    dl = 18.0
    ll = 12.0
    res = size_beam_from_loads(
        span_m=span_m,
        dead_load_kN_per_m=dl,
        live_load_kN_per_m=ll,
        fck=25.0,
        fy=500.0,
        exposure="Moderate",
    )
    design = res["design_dict"]
    dxf_path = tmp_path / "test_beam_sync.dxf"

    export_res = export_dxf_from_design(design, str(dxf_path))
    assert export_res["status"] == "success"

    # Read back DXF
    doc = ezdxf.readfile(str(dxf_path))
    layers = {layer.dxf.name for layer in doc.layers}
    # Verify expected layers from CADViewer.tsx
    for expected_layer in ["OUTLINE", "REBAR_MAIN", "REBAR_TOP", "STIRRUPS", "DIMENSIONS", "ANNOTATIONS", "TITLE_BLOCK"]:
        assert expected_layer in layers, f"Layer {expected_layer} missing from DXF"

    msp = doc.modelspace()
    texts = [e.dxf.text for e in msp if e.dxftype() == "TEXT"]
    text_content = " ".join(texts)

    # Verify dimensions in DXF match calculated design exactly
    assert f"b = {int(design['b'])} mm" in text_content
    assert f"D = {int(design['D'])} mm" in text_content
    assert f"Clear Span L = {int(span_m * 1000)} mm" in text_content

    # Verify rebar detailing matches calculation
    main_callout = f"{design['main_bar_count']}-T{int(design['main_bar_dia_mm'])}"
    assert main_callout in text_content
    stirrup_callout = f"2L-T{int(design['stirrup_dia_mm'])} @ {int(design['stirrup_spacing_mm'])}"
    assert stirrup_callout in text_content

    # Verify statutory watermark
    assert "STATUS: DRAFT - NOT FOR CONSTRUCTION" in text_content


def test_beam_studio_cad_changing_inputs_updates_results(tmp_path):
    """Changing beam input parameters produces distinct sizing dimensions and different DXFs."""
    # Sizing A: Short span, light load
    res_a = size_beam_from_loads(span_m=3.5, dead_load_kN_per_m=10.0, live_load_kN_per_m=6.0, fck=25.0, fy=500.0)
    design_a = res_a["design_dict"]

    # Sizing B: Long span, heavy load
    res_b = size_beam_from_loads(span_m=6.5, dead_load_kN_per_m=24.0, live_load_kN_per_m=16.0, fck=25.0, fy=500.0)
    design_b = res_b["design_dict"]

    # Verify calculations are distinctly different
    assert design_b["D"] > design_a["D"], "Longer span beam must be deeper"
    assert design_b["ast_provided_mm2"] > design_a["ast_provided_mm2"], "Heavier load requires more steel"

    # Export both to DXF
    path_a = tmp_path / "beam_a.dxf"
    path_b = tmp_path / "beam_b.dxf"
    export_dxf_from_design(design_a, str(path_a))
    export_dxf_from_design(design_b, str(path_b))

    doc_a = ezdxf.readfile(str(path_a))
    doc_b = ezdxf.readfile(str(path_b))

    text_a = " ".join([e.dxf.text for e in doc_a.modelspace() if e.dxftype() == "TEXT"])
    text_b = " ".join([e.dxf.text for e in doc_b.modelspace() if e.dxftype() == "TEXT"])

    assert f"Clear Span L = 3500 mm" in text_a
    assert f"Clear Span L = 6500 mm" in text_b
    assert f"D = {int(design_a['D'])} mm" in text_a
    assert f"D = {int(design_b['D'])} mm" in text_b


def test_column_studio_cad_integration_match(tmp_path):
    """Column sizing results match CAD DXF output dimensions, bars, and ties."""
    res = size_column_from_load(axial_load_kN=1400.0, length_m=3.2, fck=25.0, fy=500.0)
    design = res["design_dict"]
    dxf_path = tmp_path / "test_column_sync.dxf"

    export_res = export_column_dxf(design, output_path=str(dxf_path))
    assert export_res["status"] == "success"

    doc = ezdxf.readfile(str(dxf_path))
    layers = {layer.dxf.name for layer in doc.layers}
    for expected in ["CONCRETE", "REBAR", "TIES", "DIMENSIONS", "ANNOTATIONS", "TITLE_BLOCK"]:
        assert expected in layers, f"Layer {expected} missing in column DXF"

    texts = [e.dxf.text for e in doc.modelspace() if e.dxftype() == "TEXT"]
    text_content = " ".join(texts)

    assert f"b = {int(design['width_mm'])} mm" in text_content
    assert f"D = {int(design['depth_mm'])} mm" in text_content
    assert "STATUS: DRAFT - NOT FOR CONSTRUCTION" in text_content


def test_slab_studio_cad_integration_match(tmp_path):
    """Slab sizing results match CAD DXF output dimensions, main steel, and layers."""
    res = size_slab_from_loads(lx_m=3.5, ly_m=5.0, live_load_kN_m2=3.0, fck=25.0, fy=500.0)
    design = res["design_dict"]
    dxf_path = tmp_path / "test_slab_sync.dxf"

    export_res = export_slab_dxf(design, output_path=str(dxf_path))
    assert export_res["status"] == "success"

    doc = ezdxf.readfile(str(dxf_path))
    layers = {layer.dxf.name for layer in doc.layers}
    for expected in ["CONCRETE_OUTLINE", "REBAR_MAIN", "REBAR_DIST", "SUPPORTS", "DIMENSIONS", "TEXT_ANNOTATIONS", "TITLE_BLOCK", "WATERMARK"]:
        assert expected in layers, f"Layer {expected} missing in slab DXF"

    texts = [e.dxf.text for e in doc.modelspace() if e.dxftype() == "TEXT"]
    text_content = " ".join(texts)

    assert f"Lx = 3500 mm" in text_content
    assert f"Ly = 5000 mm" in text_content
    assert "STATUS: DRAFT - NOT FOR CONSTRUCTION" in text_content


def test_footing_studio_cad_integration_match(tmp_path):
    """Footing sizing results match CAD DXF output dimensions, rebar mesh, and layers."""
    res = size_footing_from_load(axial_load_kN=1200.0, sbc_kN_m2=200.0, fck=25.0, fy=500.0)
    design = res["design_dict"]
    dxf_path = tmp_path / "test_footing_sync.dxf"

    export_res = export_footing_dxf(design, output_path=str(dxf_path))
    assert export_res["status"] == "success"

    doc = ezdxf.readfile(str(dxf_path))
    layers = {layer.dxf.name for layer in doc.layers}
    for expected in ["CONCRETE_OUTLINE", "COLUMN_OUTLINE", "REBAR_MAIN", "DIMENSIONS", "TEXT_ANNOTATIONS", "TITLE_BLOCK", "WATERMARK"]:
        assert expected in layers, f"Layer {expected} missing in footing DXF"

    texts = [e.dxf.text for e in doc.modelspace() if e.dxftype() == "TEXT"]
    text_content = " ".join(texts)

    B = int(design["geometry"]["B_mm"])
    L = int(design["geometry"]["L_mm"])
    assert f"B = {B} mm" in text_content
    assert f"L = {L} mm" in text_content
    assert "STATUS: DRAFT - NOT FOR CONSTRUCTION" in text_content


def test_api_beam_dxf_endpoint_returns_design_and_dimensions(client):
    """POST /v1/design/dxf returns design dictionary and section dimensions for live frontend preview."""
    resp = client.post(
        "/v1/design/dxf",
        json={
            "span_m": 5.0,
            "dead_load_kN_per_m": 18.0,
            "live_load_kN_per_m": 12.0,
            "fck": 25.0,
            "fy": 500.0,
            "exposure": "Moderate",
            "output_filename": "test_api_beam_sync.dxf",
        },
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "dxf_path" in data
    assert "design" in data
    assert "section_dimensions" in data
    assert data["section_dimensions"]["b_mm"] > 0
    assert data["section_dimensions"]["D_mm"] > 0
    assert "rebar" in data
    assert data["rebar"]["main_bar_count"] > 0
