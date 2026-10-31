"""
IS 456:2000 Reinforced Concrete Isolated Footing 2D CAD Drafting Engine.

Pillar 1: Full Building Frame Members - Foundation Footings (IS 456 Cl. 34).

Generates professional AutoCAD DXF drawings for isolated RC footings:
1. Plan View showing:
   - Footing outer boundary B x L
   - Centered column outline cx x cy
   - Bottom reinforcement mesh grid in both directions
   - Dimension strings and callouts
2. Elevation Cross-Section showing:
   - Footing depth D and edge thickness
   - Column pedestal and dowel starter bars extending with 90-degree anchor bends
   - 50mm nominal bottom & side clear cover
   - Bottom tension mesh
3. Title block with project metadata and mandatory draft stamp:
   'STATUS: DRAFT - NOT FOR CONSTRUCTION. Not engineer-reviewed.'

Uses ezdxf library.
"""

from pathlib import Path
from typing import Dict, Any, Optional
import ezdxf
from ezdxf import colors


DRAFT_WATERMARK_TEXT = "STATUS: DRAFT - NOT FOR CONSTRUCTION. Not engineer-reviewed."


def create_footing_layers(doc: ezdxf.document.Drawing) -> None:
    """Configures professional CAD drafting layers with standard colors and lineweights."""
    layers = [
        {"name": "CONCRETE_OUTLINE", "color": colors.WHITE, "lineweight": 35},
        {"name": "COLUMN_OUTLINE", "color": colors.CYAN, "lineweight": 35},
        {"name": "REBAR_MAIN", "color": colors.RED, "lineweight": 50},
        {"name": "DIMENSIONS", "color": colors.CYAN, "lineweight": 18},
        {"name": "TEXT_ANNOTATIONS", "color": colors.YELLOW, "lineweight": 25},
        {"name": "TITLE_BLOCK", "color": colors.MAGENTA, "lineweight": 35},
        {"name": "WATERMARK", "color": colors.RED, "lineweight": 70},
    ]
    for lay in layers:
        if lay["name"] not in doc.layers:
            doc.layers.add(
                lay["name"],
                color=lay["color"],
                lineweight=lay["lineweight"],
            )


def draw_footing_plan(
    msp,
    origin_x: float,
    origin_y: float,
    B_mm: float,
    L_mm: float,
    col_b_mm: float,
    col_D_mm: float,
    rebar_callout: str,
    bar_dia_mm: float,
    bar_count: int,
) -> None:
    """Draws plan view of the isolated footing with column outline and bottom mesh."""
    ox = origin_x
    oy = origin_y

    # Footing boundary
    footing_pts = [
        (ox, oy),
        (ox + B_mm, oy),
        (ox + B_mm, oy + L_mm),
        (ox, oy + L_mm),
        (ox, oy),
    ]
    msp.add_lwpolyline(footing_pts, dxfattribs={"layer": "CONCRETE_OUTLINE"})

    # Centered column outline
    col_x = ox + (B_mm - col_b_mm) / 2.0
    col_y = oy + (L_mm - col_D_mm) / 2.0
    col_pts = [
        (col_x, col_y),
        (col_x + col_b_mm, col_y),
        (col_x + col_b_mm, col_y + col_D_mm),
        (col_x, col_y + col_D_mm),
        (col_x, col_y),
    ]
    msp.add_lwpolyline(col_pts, dxfattribs={"layer": "COLUMN_OUTLINE"})

    # Rebar grid (bottom mesh)
    cover = 50.0
    # X-direction bars (horizontal lines)
    if bar_count > 1:
        step_y = (L_mm - 2.0 * cover) / (bar_count - 1)
        for i in range(bar_count):
            by = oy + cover + i * step_y
            msp.add_line((ox + cover, by), (ox + B_mm - cover, by), dxfattribs={"layer": "REBAR_MAIN"})

    # Y-direction bars (vertical lines)
    if bar_count > 1:
        step_x = (B_mm - 2.0 * cover) / (bar_count - 1)
        for i in range(bar_count):
            bx = ox + cover + i * step_x
            msp.add_line((bx, oy + cover), (bx, oy + L_mm - cover), dxfattribs={"layer": "REBAR_MAIN"})

    # Dimensions
    dim_y = oy - 100.0
    msp.add_line((ox, dim_y), (ox + B_mm, dim_y), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_line((ox, dim_y - 20), (ox, dim_y + 20), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_line((ox + B_mm, dim_y - 20), (ox + B_mm, dim_y + 20), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_text(
        f"B = {int(B_mm)} mm",
        height=35.0,
        dxfattribs={"layer": "DIMENSIONS"},
    ).set_placement((ox + (B_mm / 2.0) - 100.0, dim_y - 45.0))

    dim_x = ox - 100.0
    msp.add_line((dim_x, oy), (dim_x, oy + L_mm), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_line((dim_x - 20, oy), (dim_x + 20, oy), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_line((dim_x - 20, oy + L_mm), (dim_x + 20, oy + L_mm), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_text(
        f"L = {int(L_mm)} mm",
        height=35.0,
        dxfattribs={"layer": "DIMENSIONS"},
    ).set_placement((dim_x - 120.0, oy + (L_mm / 2.0) - 10.0))

    # Column dimensions
    msp.add_text(
        f"COLUMN {int(col_b_mm)}x{int(col_D_mm)}",
        height=30.0,
        dxfattribs={"layer": "TEXT_ANNOTATIONS"},
    ).set_placement((col_x - 30.0, col_y + col_D_mm + 25.0))

    # Rebar Callout
    msp.add_text(
        f"BOTTOM MESH: {rebar_callout} (BOTH WAYS)",
        height=30.0,
        dxfattribs={"layer": "TEXT_ANNOTATIONS"},
    ).set_placement((ox + 50.0, oy + L_mm - 50.0))

    # Plan Title
    msp.add_text(
        "FOOTING PLAN VIEW (1:25)",
        height=35.0,
        dxfattribs={"layer": "TEXT_ANNOTATIONS"},
    ).set_placement((ox + (B_mm / 2.0) - 160.0, dim_y - 120.0))


def draw_footing_elevation(
    msp,
    origin_x: float,
    origin_y: float,
    B_mm: float,
    D_mm: float,
    col_b_mm: float,
    rebar_callout: str,
) -> None:
    """Draws elevation cross-section showing depth D, pedestal, and rebar mesh."""
    ox = origin_x
    oy = origin_y

    # Footing concrete cross-section (stepped/trapezoidal or uniform)
    col_x_left = ox + (B_mm - col_b_mm) / 2.0
    col_x_right = col_x_left + col_b_mm
    column_height = 500.0  # height of column stub above footing

    footing_pts = [
        (ox, oy),
        (ox + B_mm, oy),
        (ox + B_mm, oy + D_mm),
        (col_x_right, oy + D_mm),
        (col_x_right, oy + D_mm + column_height),
        (col_x_left, oy + D_mm + column_height),
        (col_x_left, oy + D_mm),
        (ox, oy + D_mm),
        (ox, oy),
    ]
    msp.add_lwpolyline(footing_pts, dxfattribs={"layer": "CONCRETE_OUTLINE"})

    # Bottom Reinforcement Mat (Continuous rod with 90-degree end hooks)
    cover = 50.0
    mat_y = oy + cover
    msp.add_line((ox + cover, mat_y), (ox + B_mm - cover, mat_y), dxfattribs={"layer": "REBAR_MAIN"})
    # Hook bends
    hook_len = min(150.0, D_mm - 2.0 * cover)
    msp.add_line((ox + cover, mat_y), (ox + cover, mat_y + hook_len), dxfattribs={"layer": "REBAR_MAIN"})
    msp.add_line((ox + B_mm - cover, mat_y), (ox + B_mm - cover, mat_y + hook_len), dxfattribs={"layer": "REBAR_MAIN"})

    # Column Starter Bars / Dowels extending into footing and bent out 90°
    dowel_left_x = col_x_left + 40.0
    dowel_right_x = col_x_right - 40.0
    # Left dowel
    msp.add_line((dowel_left_x, oy + D_mm + column_height), (dowel_left_x, mat_y + 20.0), dxfattribs={"layer": "REBAR_MAIN"})
    msp.add_line((dowel_left_x, mat_y + 20.0), (dowel_left_x + 200.0, mat_y + 20.0), dxfattribs={"layer": "REBAR_MAIN"})
    # Right dowel
    msp.add_line((dowel_right_x, oy + D_mm + column_height), (dowel_right_x, mat_y + 20.0), dxfattribs={"layer": "REBAR_MAIN"})
    msp.add_line((dowel_right_x, mat_y + 20.0), (dowel_right_x - 200.0, mat_y + 20.0), dxfattribs={"layer": "REBAR_MAIN"})

    # Dimensions
    # Depth D
    dim_x = ox + B_mm + 80.0
    msp.add_line((dim_x, oy), (dim_x, oy + D_mm), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_line((dim_x - 15, oy), (dim_x + 15, oy), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_line((dim_x - 15, oy + D_mm), (dim_x + 15, oy + D_mm), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_text(
        f"D = {int(D_mm)} mm",
        height=30.0,
        dxfattribs={"layer": "DIMENSIONS"},
    ).set_placement((dim_x + 25.0, oy + (D_mm / 2.0) - 10.0))

    # Width B
    dim_y = oy - 80.0
    msp.add_line((ox, dim_y), (ox + B_mm, dim_y), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_line((ox, dim_y - 15), (ox, dim_y + 15), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_line((ox + B_mm, dim_y - 15), (ox + B_mm, dim_y + 15), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_text(
        f"WIDTH B = {int(B_mm)} mm",
        height=30.0,
        dxfattribs={"layer": "DIMENSIONS"},
    ).set_placement((ox + (B_mm / 2.0) - 120.0, dim_y - 40.0))

    # Elevation Title
    msp.add_text(
        "CROSS-SECTION ELEVATION (1:25)",
        height=35.0,
        dxfattribs={"layer": "TEXT_ANNOTATIONS"},
    ).set_placement((ox + (B_mm / 2.0) - 200.0, dim_y - 100.0))


def draw_footing_title_block(
    msp,
    origin_x: float,
    origin_y: float,
    width: float = 1100.0,
    height: float = 240.0,
    project_title: str = "IS 456 RC ISOLATED FOOTING DESIGN",
    details: str = "2.00m x 2.00m x 450mm Footing",
) -> None:
    """Draws standard engineer title block with mandatory draft disclaimer."""
    ox = origin_x
    oy = origin_y

    pts = [
        (ox, oy),
        (ox + width, oy),
        (ox + width, oy + height),
        (ox, oy + height),
        (ox, oy),
    ]
    msp.add_lwpolyline(pts, dxfattribs={"layer": "TITLE_BLOCK"})

    msp.add_line((ox, oy + 160.0), (ox + width, oy + 160.0), dxfattribs={"layer": "TITLE_BLOCK"})
    msp.add_line((ox, oy + 80.0), (ox + width, oy + 80.0), dxfattribs={"layer": "TITLE_BLOCK"})

    msp.add_text(project_title, height=22.0, dxfattribs={"layer": "TEXT_ANNOTATIONS"}).set_placement((ox + 20.0, oy + 185.0))
    msp.add_text(details, height=18.0, dxfattribs={"layer": "TEXT_ANNOTATIONS"}).set_placement((ox + 20.0, oy + 115.0))
    msp.add_text(
        "CODE: IS 456:2000 | UNITS: mm | COVER: 50mm | GRADE: M25 / Fe500",
        height=14.0,
        dxfattribs={"layer": "TEXT_ANNOTATIONS"},
    ).set_placement((ox + 20.0, oy + 95.0))

    # Watermark Draft Stamp
    msp.add_text(
        DRAFT_WATERMARK_TEXT,
        height=16.0,
        dxfattribs={"layer": "WATERMARK"},
    ).set_placement((ox + 20.0, oy + 35.0))


def export_footing_dxf(
    design: Dict[str, Any],
    output_path: Optional[str] = None,
    output_filename: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Exports complete AutoCAD DXF file for a designed RC isolated footing.
    Supports either output_path or output_filename keyword arguments.
    """
    dest_path = output_path or output_filename or kwargs.get("filepath") or "footing_design.dxf"
    out_file = Path(dest_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    doc = ezdxf.new("R2010")
    doc.units = 4  # Millimetres
    doc.header["$INSUNITS"] = 4
    create_footing_layers(doc)
    msp = doc.modelspace()

    geom = design["geometry"]
    col = design["column"]
    flex = design["flexure"]
    rebar = flex["rebar_mesh"]

    B_mm = float(geom["B_mm"])
    L_mm = float(geom["L_mm"])
    D_mm = float(geom["total_depth_D_mm"])
    col_b_mm = float(col["b_mm"])
    col_D_mm = float(col["D_mm"])

    # 1. Plan View
    draw_footing_plan(
        msp=msp,
        origin_x=0.0,
        origin_y=0.0,
        B_mm=B_mm,
        L_mm=L_mm,
        col_b_mm=col_b_mm,
        col_D_mm=col_D_mm,
        rebar_callout=rebar["callout"],
        bar_dia_mm=float(rebar["bar_dia_mm"]),
        bar_count=int(rebar["bar_count"]),
    )

    # 2. Elevation View (positioned to the right)
    elev_ox = B_mm + 500.0
    elev_oy = 0.0
    draw_footing_elevation(
        msp=msp,
        origin_x=elev_ox,
        origin_y=elev_oy,
        B_mm=B_mm,
        D_mm=D_mm,
        col_b_mm=col_b_mm,
        rebar_callout=rebar["callout"],
    )

    # 3. Title Block (positioned below)
    tb_ox = 0.0
    tb_oy = -550.0
    summary_txt = f"{int(B_mm)}x{int(L_mm)}x{int(D_mm)} mm (Col: {int(col_b_mm)}x{int(col_D_mm)}, Load: {col['axial_load_kN']} kN)"
    draw_footing_title_block(
        msp=msp,
        origin_x=tb_ox,
        origin_y=tb_oy,
        width=1100.0,
        height=240.0,
        project_title="IS 456 RC ISOLATED FOOTING DESIGN",
        details=summary_txt,
    )

    doc.saveas(str(out_file))

    return {
        "status": "success",
        "dxf_path": str(out_file.resolve()),
        "plan_dimensions": f"{int(B_mm)}x{int(L_mm)} mm",
        "total_depth": f"{int(D_mm)} mm",
        "reinforcement": rebar["callout"],
        "approval_status": "DRAFT - NOT FOR CONSTRUCTION",
    }
