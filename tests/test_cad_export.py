"""
Unit tests for IS 456 2D CAD DXF Drawing Generator (src/cad/beam_dxf.py).
Validates layer setup, CAD entities, IS 456 annotations, file generation,
millimetre units ($INSUNITS = 4), symmetric stirrups, and d dimension consistency.
Does NOT read .env or call external networks.
"""

from pathlib import Path
import pytest
import ezdxf

from src.cad.beam_dxf import (
    generate_beam_dxf,
    export_dxf_from_design,
    export_dxf_from_loads,
    compute_symmetric_stirrup_positions,
    LAYERS_CONFIG,
)

SAMPLE_VALID_DESIGN = {
    "b": 300.0,
    "D": 500.0,
    "d": 450.0,
    "fck": 25.0,
    "fy": 500.0,
    "exposure": "Moderate",
    "main_bar_dia_mm": 16.0,
    "main_bar_count": 3,
    "compression_bar_dia_mm": 10.0,
    "compression_bar_count": 2,
    "stirrup_dia_mm": 8.0,
    "stirrup_spacing_mm": 150.0,
    "span_m": 4.5,
}


def test_generate_beam_dxf_layers_and_entities():
    """DXF drawing contains all required engineering layers, entities, and millimetre units."""
    doc = generate_beam_dxf(SAMPLE_VALID_DESIGN)
    assert doc is not None

    # Check units: millimetres (4)
    assert doc.units == 4
    assert doc.header["$INSUNITS"] == 4

    # Verify all layers are registered
    existing_layers = {layer.dxf.name for layer in doc.layers}
    for req_layer in LAYERS_CONFIG.keys():
        assert req_layer in existing_layers, f"Missing layer: {req_layer}"

    msp = doc.modelspace()
    entities = list(msp)
    assert len(entities) > 30, f"Expected rich drawing with entities, got {len(entities)}"

    # Check entity types
    entity_types = {e.dxftype() for e in entities}
    assert "LINE" in entity_types
    assert "CIRCLE" in entity_types
    assert "LWPOLYLINE" in entity_types
    assert "TEXT" in entity_types


def test_dxf_annotations_and_disclaimer():
    """Text entities in DXF must explicitly cite IS 456, include disclaimer, and updated Note 8."""
    doc = generate_beam_dxf(SAMPLE_VALID_DESIGN)
    msp = doc.modelspace()

    texts = [e.dxf.text for e in msp if e.dxftype() == "TEXT"]
    combined_text = " ".join(texts)

    # Citations required by Step 8
    assert "IS 456:2000" in combined_text
    assert "Cl. 26.5.1.1" in combined_text
    assert "Cl. 26.5.1.5" in combined_text or "26.5.1.6" in combined_text
    assert "Table 16" in combined_text
    assert "SECTION A-A" in combined_text
    assert "LONGITUDINAL ELEVATION" in combined_text

    # Item 1: Title block disclaimer text
    assert "STATUS: DRAFT - NOT FOR CONSTRUCTION" in combined_text
    assert "Passes the implemented IS 456 beam detailing checks only" in combined_text
    assert "Must be reviewed and signed by a structural engineer" in combined_text
    assert "STATUS: FULLY VERIFIED & CODE COMPLIANT" not in combined_text

    # Item 2: Note 8 replacement
    assert "8. Development and lap lengths: as per IS 456:2000 Cl. 26.2, to be specified by the structural engineer (not computed by this tool)." in combined_text
    assert "50 * bar diameter" not in combined_text


def test_symmetric_stirrup_layout():
    """Stirrup layout is symmetric about mid-span with first stirrups 50 mm from support face, max gap <= design spacing."""
    test_cases = [
        (4000.0, 300.0, 150.0),
        (4500.0, 300.0, 150.0),
        (5000.0, 300.0, 150.0),
        (5000.0, 300.0, 200.0),
        (5000.0, 300.0, 300.0),
        (6000.0, 300.0, 250.0),
    ]

    for span_mm, sup_w, spacing in test_cases:
        positions = compute_symmetric_stirrup_positions(
            span_mm=span_mm,
            support_width_mm=sup_w,
            stirrup_spacing=spacing,
        )
        assert len(positions) >= 2

        # 1. First stirrup is 50 mm from each support face
        assert abs(positions[0] - (sup_w + 50.0)) < 1e-4
        assert abs(positions[-1] - (sup_w + span_mm - 50.0)) < 1e-4

        # 2. Symmetric about mid-span
        mid_x = sup_w + span_mm / 2.0
        n = len(positions)
        for i in range(n):
            sym_mid = (positions[i] + positions[n - 1 - i]) / 2.0
            assert abs(sym_mid - mid_x) < 1e-4, f"Asymmetry at index {i}: {positions[i]}, {positions[n-1-i]}"

        # 3. No gap larger than design spacing
        gaps = [positions[i + 1] - positions[i] for i in range(n - 1)]
        assert max(gaps) <= spacing + 1e-4, f"Gap {max(gaps)} exceeds design spacing {spacing}"
        assert min(gaps) > 0.0

    # Also test actual DXF longitudinal elevation stirrup lines
    doc = generate_beam_dxf(SAMPLE_VALID_DESIGN)
    msp = doc.modelspace()
    elevation_x = SAMPLE_VALID_DESIGN["b"] + 500.0
    stirrup_lines = [
        e for e in msp
        if e.dxftype() == "LINE"
        and e.dxf.layer == "STIRRUPS"
        and e.dxf.start.x > elevation_x
    ]
    assert len(stirrup_lines) >= 10
    x_coords = sorted({round(l.dxf.start.x, 3) for l in stirrup_lines})
    dxf_mid_x = elevation_x + 300.0 + (SAMPLE_VALID_DESIGN["span_m"] * 1000.0) / 2.0
    for i in range(len(x_coords)):
        assert abs((x_coords[i] + x_coords[len(x_coords) - 1 - i]) / 2.0 - dxf_mid_x) < 1e-4

    dxf_gaps = [x_coords[i + 1] - x_coords[i] for i in range(len(x_coords) - 1)]
    assert max(dxf_gaps) <= SAMPLE_VALID_DESIGN["stirrup_spacing_mm"] + 1e-4


def test_d_dimension_and_bar_position_consistency():
    """The d dimension is drawn from the compression face to the centroid of the bottom bars as drawn."""
    doc = generate_beam_dxf(SAMPLE_VALID_DESIGN)
    msp = doc.modelspace()

    # In SAMPLE_VALID_DESIGN: D = 500, cover = 30, stirrup_dia = 8, main_dia = 16
    # Centroid of bottom bars: bot_y = 30 + 8 + 16/2 = 46.0 mm from bottom
    # Distance from compression face (top = 500 mm) to centroid of bottom bars = 500 - 46 = 454.0 mm
    expected_d_drawn = 500.0 - (30.0 + 8.0 + 16.0 / 2.0)  # 454.0 mm

    # Find the text entity displaying "d = "
    d_texts = [e.dxf.text for e in msp if e.dxftype() == "TEXT" and "d =" in e.dxf.text and "mm" in e.dxf.text]
    assert len(d_texts) >= 1
    assert f"d = {int(round(expected_d_drawn))} mm" in d_texts[0]


def test_export_dxf_from_design_file_io(tmp_path: Path):
    """export_dxf_from_design writes valid DXF file that can be reopened."""
    out_file = str(tmp_path / "test_beam.dxf")
    res = export_dxf_from_design(SAMPLE_VALID_DESIGN, output_path=out_file, validate_first=True)

    assert res["status"] == "success"
    assert Path(out_file).exists()
    assert Path(out_file).stat().st_size > 1000

    # Reopen file with ezdxf to verify integrity
    reopened_doc = ezdxf.readfile(out_file)
    assert reopened_doc is not None
    assert reopened_doc.units == 4
    assert reopened_doc.header["$INSUNITS"] == 4
    assert len(reopened_doc.layers) >= 5


def test_export_dxf_rejects_non_compliant_design(tmp_path: Path):
    """export_dxf_from_design halts export if design fails deterministic IS 456 checks."""
    invalid_design = dict(SAMPLE_VALID_DESIGN)
    # Stirrup spacing = 600 mm (exceeds max spacing 300 mm per Cl. 26.5.1.5)
    invalid_design["stirrup_spacing_mm"] = 600.0

    out_file = str(tmp_path / "invalid_beam.dxf")
    res = export_dxf_from_design(invalid_design, output_path=out_file, validate_first=True)

    assert res["status"] == "failed_validation"
    assert res["dxf_path"] is None
    assert not Path(out_file).exists()


def test_export_dxf_from_loads_end_to_end(tmp_path: Path):
    """End-to-End: Span & Loads -> Sizing -> Checks -> DXF Export."""
    out_file = str(tmp_path / "loads_beam.dxf")
    res = export_dxf_from_loads(
        span_m=5.0,
        dead_load_kN_per_m=12.0,
        live_load_kN_per_m=8.0,
        fck=25.0,
        fy=500.0,
        exposure="Moderate",
        output_path=out_file,
    )

    assert res["status"] == "success"
    assert Path(out_file).exists()
    assert res["sizing"]["section_dimensions"]["b"] in [230.0, 300.0]
    assert res["validation"]["status"] == "passed"

    # Reopen to confirm validity
    doc = ezdxf.readfile(out_file)
    assert doc.units == 4
    assert doc.header["$INSUNITS"] == 4
    assert len(list(doc.modelspace())) > 20


def test_cad_export_shear_status_incomplete_dxf(tmp_path: Path):
    """
    DXF export reflects shear_status:
    - If 'needs_shear_design', title block marks INCOMPLETE and stirrup note warns.
    - If 'stirrups_designed' or 'minimum_shear_steel', standard draft disclaimer is displayed without incomplete warnings.
    """
    # 1. Incomplete shear case -> needs_shear_design
    incomplete_design = dict(SAMPLE_VALID_DESIGN)
    incomplete_design["shear_status"] = "needs_shear_design"
    incomplete_file = str(tmp_path / "incomplete_shear_beam.dxf")
    res_inc = export_dxf_from_design(incomplete_design, output_path=incomplete_file, validate_first=False)
    assert res_inc["status"] == "success"

    doc_inc = ezdxf.readfile(incomplete_file)
    texts_inc = [e.dxf.text for e in doc_inc.modelspace() if e.dxftype() == "TEXT"]
    combined_inc = " ".join(texts_inc)

    assert "STATUS: INCOMPLETE - SHEAR DESIGN REQUIRED (IS 456 Cl. 40.4). NOT FOR CONSTRUCTION." in combined_inc
    assert "Stirrup spacing NOT designed for shear" in combined_inc

    # 2. Designed shear case -> stirrups_designed
    designed_file = str(tmp_path / "designed_shear_beam.dxf")
    res_designed = export_dxf_from_loads(
        span_m=5.0,
        dead_load_kN_per_m=15.0,
        live_load_kN_per_m=10.0,
        fck=25.0,
        fy=500.0,
        exposure="Moderate",
        output_path=designed_file,
    )
    assert res_designed["status"] == "success"
    assert res_designed["shear_status"] == "stirrups_designed"

    doc_des = ezdxf.readfile(designed_file)
    texts_des = [e.dxf.text for e in doc_des.modelspace() if e.dxftype() == "TEXT"]
    combined_des = " ".join(texts_des)

    assert "STATUS: DRAFT - NOT FOR CONSTRUCTION" in combined_des
    assert "STATUS: INCOMPLETE - SHEAR DESIGN REQUIRED" not in combined_des
    assert "Stirrup spacing NOT designed for shear" not in combined_des

