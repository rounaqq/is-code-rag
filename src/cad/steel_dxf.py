"""
2D CAD DXF Drafting Engine for IS 800:2007 Structural Steel Details.
Generates vector DXF drawings including:
  1. Gusset Plate Bolted / Welded Connection Detail (plate outline, bolt group,
     connected member, weld symbols, dimensions)
  2. Truss Elevation (chords, verticals, diagonals, panel points, member callouts)
  3. Standard Title Block carrying the mandatory draft status:
     "STATUS: DRAFT - NOT FOR CONSTRUCTION. Not engineer-reviewed."
Geometry only: no IS 800 member capacities or bolt capacities are evaluated in this
module, so every drawing must still be verified by a structural engineer.
Zero proprietary software required; uses open standard ezdxf.
"""

from pathlib import Path
from typing import Dict, Any, List

import ezdxf
from ezdxf import colors


DRAFT_WATERMARK_TEXT = "STATUS: DRAFT - NOT FOR CONSTRUCTION. Not engineer-reviewed."

_LAYERS = [
    ("STEEL", colors.WHITE, "CONTINUOUS"),
    ("BOLTS", colors.RED, "CONTINUOUS"),
    ("WELDS", colors.MAGENTA, "CONTINUOUS"),
    ("DIMENSIONS", colors.GREEN, "CONTINUOUS"),
    ("ANNOTATIONS", colors.YELLOW, "CONTINUOUS"),
    ("TITLE_BLOCK", colors.WHITE, "CONTINUOUS"),
    ("WATERMARK", colors.RED, "CONTINUOUS"),
]


def _new_doc():
    """Creates a new R2010 DXF document with the standard steel detailing layers and mm units."""
    doc = ezdxf.new("R2010")
    doc.units = 4  # Millimetres
    doc.header["$INSUNITS"] = 4
    for name, color, linetype in _LAYERS:
        if name not in doc.layers:
            doc.layers.add(name=name, color=color, linetype=linetype)
    return doc


def _draw_title_block(
    msp,
    x: float,
    y: float,
    width: float,
    title: str,
    detail_lines: List[str],
    approval_status: str,
) -> None:
    """Draws the standard title block holding the draft status watermark."""
    height = 170.0
    msp.add_lwpolyline(
        [(x, y), (x + width, y), (x + width, y + height), (x, y + height), (x, y)],
        dxfattribs={"layer": "TITLE_BLOCK"},
    )
    msp.add_text(title, dxfattribs={"layer": "TITLE_BLOCK", "height": 22}).set_placement((x + 20, y + 130))
    row = y + 100.0
    for line in detail_lines:
        msp.add_text(line, dxfattribs={"layer": "TITLE_BLOCK", "height": 16}).set_placement((x + 20, row))
        row -= 28.0
    msp.add_text(approval_status, dxfattribs={"layer": "WATERMARK", "height": 18}).set_placement((x + 20, y + 25))


def export_steel_connection_dxf(
    design: Dict[str, Any],
    output_path: str,
) -> Dict[str, Any]:
    """
    Exports a gusset plate connection detail as a 2D AutoCAD DXF drawing.

    The drawing is geometry only and carries no IS 800 capacity claim; it shows the
    plate outline, the bolt group at the given pitch and gauge, the connected member,
    and the weld symbol for the requested weld type.
    """
    plate_w = float(design.get("plate_width_mm", 250.0))
    plate_h = float(design.get("plate_height_mm", 300.0))
    plate_t = float(design.get("plate_thickness_mm", 10.0))

    bolt_dia = float(design.get("bolt_dia_mm", 20.0))
    bolt_rows = max(1, int(design.get("bolt_rows", 2)))
    bolt_cols = max(1, int(design.get("bolt_cols", 2)))
    pitch = float(design.get("bolt_pitch_mm", 80.0))
    gauge = float(design.get("bolt_gauge_mm", 60.0))
    edge = float(design.get("edge_distance_mm", 40.0))

    weld_type = str(design.get("weld_type", "fillet")).strip().lower()
    weld_size = float(design.get("weld_size_mm", 6.0))
    member_label = str(design.get("member_label", "ISA 75x75x6"))
    member_depth = float(design.get("member_depth_mm", 75.0))

    approval_status = design.get("approval_status", DRAFT_WATERMARK_TEXT)

    doc = _new_doc()
    msp = doc.modelspace()

    # -------------------------------------------------------------------------
    # 1. GUSSET PLATE OUTLINE
    # -------------------------------------------------------------------------
    msp.add_lwpolyline(
        [(0, 0), (plate_w, 0), (plate_w, plate_h), (0, plate_h), (0, 0)],
        dxfattribs={"layer": "STEEL"},
    )

    # -------------------------------------------------------------------------
    # 2. BOLT GROUP (centred on the plate)
    # -------------------------------------------------------------------------
    hole_radius = bolt_dia / 2.0
    group_w = gauge * (bolt_cols - 1)
    group_h = pitch * (bolt_rows - 1)
    start_x = (plate_w - group_w) / 2.0
    start_y = (plate_h - group_h) / 2.0

    bolt_positions: List[tuple] = []
    for i in range(bolt_cols):
        bx = start_x + (i * gauge)
        for j in range(bolt_rows):
            by = start_y + (j * pitch)
            bolt_positions.append((bx, by))

    for bx, by in bolt_positions:
        msp.add_circle((bx, by), radius=hole_radius, dxfattribs={"layer": "BOLTS"})
        cross = max(hole_radius * 1.6, 10.0)
        msp.add_line((bx - cross, by), (bx + cross, by), dxfattribs={"layer": "BOLTS"})
        msp.add_line((bx, by - cross), (bx, by + cross), dxfattribs={"layer": "BOLTS"})

    # -------------------------------------------------------------------------
    # 3. CONNECTED MEMBER (butting the left edge of the plate)
    # -------------------------------------------------------------------------
    mem_y0 = (plate_h / 2.0) - (member_depth / 2.0)
    mem_y1 = (plate_h / 2.0) + (member_depth / 2.0)
    mem_x0 = -300.0
    msp.add_lwpolyline(
        [(mem_x0, mem_y0), (0, mem_y0), (0, mem_y1), (mem_x0, mem_y1)],
        dxfattribs={"layer": "STEEL"},
    )
    msp.add_line((mem_x0 - 40.0, plate_h / 2.0), (0, plate_h / 2.0), dxfattribs={"layer": "ANNOTATIONS"})
    msp.add_text(member_label, dxfattribs={"layer": "ANNOTATIONS", "height": 18}).set_placement(
        (mem_x0 - 10.0, plate_h / 2.0 - 35.0)
    )

    # -------------------------------------------------------------------------
    # 4. WELD SYMBOLS along the member-to-plate interface
    # -------------------------------------------------------------------------
    weld_leg = max(weld_size * 3.0, 15.0)
    weld_ys = [mem_y0 + weld_leg, plate_h / 2.0, mem_y1 - weld_leg]
    for wy in weld_ys:
        msp.add_lwpolyline(
            [(0, wy), (weld_leg, wy), (0, wy + weld_leg), (0, wy)],
            dxfattribs={"layer": "WELDS"},
        )
    weld_note = f"{weld_type.upper()} WELD {int(weld_size)} mm"
    msp.add_line((weld_leg, plate_h / 2.0), (plate_w + 320.0, plate_h + 140.0), dxfattribs={"layer": "WELDS"})
    msp.add_text(weld_note, dxfattribs={"layer": "WELDS", "height": 16}).set_placement(
        (plate_w + 40.0, plate_h + 120.0)
    )

    # -------------------------------------------------------------------------
    # 5. DIMENSIONS
    # -------------------------------------------------------------------------
    dim_offset = 70.0
    msp.add_line((0, -dim_offset), (plate_w, -dim_offset), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_text(f"{int(plate_w)} mm", dxfattribs={"layer": "DIMENSIONS", "height": 18}).set_placement(
        (plate_w / 2.0 - 30.0, -dim_offset - 30.0)
    )

    msp.add_line((-dim_offset, 0), (-dim_offset, plate_h), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_text(
        f"{int(plate_h)} mm", dxfattribs={"layer": "DIMENSIONS", "height": 18, "rotation": 90}
    ).set_placement((-dim_offset - 30.0, plate_h / 2.0 - 30.0))

    pitch_dim_x = plate_w + dim_offset
    msp.add_line((pitch_dim_x, start_y), (pitch_dim_x, start_y + group_h), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_text(
        f"pitch {int(pitch)}", dxfattribs={"layer": "DIMENSIONS", "height": 16, "rotation": 90}
    ).set_placement((pitch_dim_x + 15.0, start_y + group_h / 2.0 - 25.0))

    if bolt_cols > 1:
        gauge_dim_y = plate_h + dim_offset
        msp.add_line((start_x, gauge_dim_y), (start_x + group_w, gauge_dim_y), dxfattribs={"layer": "DIMENSIONS"})
        msp.add_text(
            f"gauge {int(gauge)}", dxfattribs={"layer": "DIMENSIONS", "height": 16}
        ).set_placement((start_x + group_w / 2.0 - 40.0, gauge_dim_y + 15.0))

    if bolt_rows > 1:
        msp.add_text(
            f"edge {int(edge)} mm", dxfattribs={"layer": "DIMENSIONS", "height": 14}
        ).set_placement((0.0, -dim_offset - 55.0))

    # -------------------------------------------------------------------------
    # 6. ANNOTATIONS AND TITLE BLOCK
    # -------------------------------------------------------------------------
    msp.add_text("GUSSET PLATE CONNECTION DETAIL", dxfattribs={"layer": "ANNOTATIONS", "height": 25}).set_placement(
        (0.0, plate_h + dim_offset + 60.0)
    )
    msp.add_text(
        f"Plate: {int(plate_w)} x {int(plate_h)} x {int(plate_t)} mm",
        dxfattribs={"layer": "ANNOTATIONS", "height": 16},
    ).set_placement((0.0, plate_h + dim_offset + 30.0))

    bolt_callout = f"{len(bolt_positions)} nos. M{int(bolt_dia)} bolts @ {int(pitch)} pitch / {int(gauge)} gauge"
    _draw_title_block(
        msp,
        x=mem_x0,
        y=-300.0,
        width=(plate_w - mem_x0) + dim_offset + 120.0,
        title="IS 800:2007 STRUCTURAL STEEL CONNECTION DETAIL",
        detail_lines=[
            f"Plate: {int(plate_w)} x {int(plate_h)} x {int(plate_t)} mm gusset",
            f"Bolts: {bolt_callout}",
            f"Weld: {weld_note}",
            f"Member: {member_label} (geometric layout only)",
        ],
        approval_status=approval_status,
    )
    msp.add_text(
        "GEOMETRY ONLY - NO IS 800 CAPACITY CHECK PERFORMED",
        dxfattribs={"layer": "WATERMARK", "height": 16},
    ).set_placement((mem_x0 + 20.0, -340.0))

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(out_file))

    return {
        "status": "success",
        "dxf_path": str(out_file),
        "detail_type": "gusset_plate_connection",
        "plate_size": f"{int(plate_w)}x{int(plate_h)}x{int(plate_t)} mm",
        "bolt_callout": bolt_callout,
        "weld": weld_note,
        "approval_status": approval_status,
    }


def export_truss_elevation_dxf(
    design: Dict[str, Any],
    output_path: str,
) -> Dict[str, Any]:
    """
    Exports a truss elevation as a 2D AutoCAD DXF drawing.

    The drawing is geometry only: it lays out the top and bottom chords, panel
    verticals, alternating diagonals and panel points at the requested span, height
    and panel count. No IS 800 member capacities are evaluated.
    """
    span_m = float(design.get("span_m", 6.0))
    height_m = float(design.get("height_m", 1.5))
    panels = max(1, int(design.get("panels", 4)))
    chord_label = str(design.get("chord_label", "ISA 75x75x6"))
    brace_label = str(design.get("brace_label", "ISA 60x60x6"))

    approval_status = design.get("approval_status", DRAFT_WATERMARK_TEXT)

    span = span_m * 1000.0
    height = height_m * 1000.0
    panel_w = span / panels

    doc = _new_doc()
    msp = doc.modelspace()

    # -------------------------------------------------------------------------
    # 1. CHORDS
    # -------------------------------------------------------------------------
    msp.add_line((0, 0), (span, 0), dxfattribs={"layer": "STEEL"})
    msp.add_line((0, height), (span, height), dxfattribs={"layer": "STEEL"})

    # -------------------------------------------------------------------------
    # 2. PANEL VERTICALS, DIAGONALS AND PANEL POINTS
    # -------------------------------------------------------------------------
    node_radius = 25.0
    for i in range(panels + 1):
        x = i * panel_w
        msp.add_line((x, 0), (x, height), dxfattribs={"layer": "STEEL"})
        msp.add_circle((x, 0), radius=node_radius, dxfattribs={"layer": "ANNOTATIONS"})
        msp.add_circle((x, height), radius=node_radius, dxfattribs={"layer": "ANNOTATIONS"})

    for i in range(panels):
        x0 = i * panel_w
        x1 = (i + 1) * panel_w
        if i % 2 == 0:
            msp.add_line((x0, 0), (x1, height), dxfattribs={"layer": "STEEL"})
        else:
            msp.add_line((x0, height), (x1, 0), dxfattribs={"layer": "STEEL"})

    # -------------------------------------------------------------------------
    # 3. SUPPORTS
    # -------------------------------------------------------------------------
    support = 60.0
    msp.add_lwpolyline([(0, 0), (-support, -support), (support, -support), (0, 0)], dxfattribs={"layer": "DIMENSIONS"})
    msp.add_lwpolyline(
        [(span, 0), (span - support, -support), (span + support, -support), (span, 0)],
        dxfattribs={"layer": "DIMENSIONS"},
    )

    # -------------------------------------------------------------------------
    # 4. DIMENSIONS
    # -------------------------------------------------------------------------
    dim_y = -160.0
    msp.add_line((0, dim_y), (span, dim_y), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_text(
        f"span = {span_m:.2f} m", dxfattribs={"layer": "DIMENSIONS", "height": 20}
    ).set_placement((span / 2.0 - 70.0, dim_y - 35.0))

    dim_x = span + 120.0
    msp.add_line((dim_x, 0), (dim_x, height), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_text(
        f"h = {height_m:.2f} m", dxfattribs={"layer": "DIMENSIONS", "height": 18, "rotation": 90}
    ).set_placement((dim_x + 20.0, height / 2.0 - 60.0))

    # -------------------------------------------------------------------------
    # 5. ANNOTATIONS AND TITLE BLOCK
    # -------------------------------------------------------------------------
    msp.add_text("TRUSS ELEVATION", dxfattribs={"layer": "ANNOTATIONS", "height": 25}).set_placement(
        (0.0, height + 120.0)
    )
    msp.add_text(
        f"Chords: {chord_label}   Braces: {brace_label}",
        dxfattribs={"layer": "ANNOTATIONS", "height": 16},
    ).set_placement((0.0, height + 90.0))
    msp.add_text(
        f"{panels} panels @ {panel_w:.0f} mm c/c",
        dxfattribs={"layer": "ANNOTATIONS", "height": 16},
    ).set_placement((0.0, height + 60.0))

    _draw_title_block(
        msp,
        x=0.0,
        y=-500.0,
        width=span + 240.0,
        title="IS 800:2007 STRUCTURAL STEEL TRUSS ELEVATION",
        detail_lines=[
            f"Span: {span_m:.2f} m, Height: {height_m:.2f} m, Panels: {panels}",
            f"Chords: {chord_label}",
            f"Braces / verticals: {brace_label}",
            "Member sizes are layout labels only (no IS 800 capacity check)",
        ],
        approval_status=approval_status,
    )
    msp.add_text(
        "GEOMETRY ONLY - NO IS 800 CAPACITY CHECK PERFORMED",
        dxfattribs={"layer": "WATERMARK", "height": 16},
    ).set_placement((20.0, -540.0))

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(out_file))

    return {
        "status": "success",
        "dxf_path": str(out_file),
        "detail_type": "truss_elevation",
        "span_m": span_m,
        "height_m": height_m,
        "panels": panels,
        "approval_status": approval_status,
    }
