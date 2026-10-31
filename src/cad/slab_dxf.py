"""
IS 456:2000 Reinforced Concrete Slab 2D CAD Drafting Engine.

Pillar 1: Full Building Frame Members - Floor Slabs (IS 456 Cl. 24 & Cl. 26.5.2).

Generates professional AutoCAD DXF drawings for concrete floor slabs:
1. Cross-Section Elevation through span showing:
   - Concrete slab thickness D and span Lx
   - Supporting masonry/RC beams on either side
   - Clear bottom cover (Table 16)
   - Main bottom tension rebar circles or continuous rods
   - Distribution/transverse rebar sitting directly on main bars
   - Dimension lines and callouts (e.g. 'T10 @ 150 mm c/c')
2. Plan View of Slab Panel with reinforcement grid layout
3. Standard ISO / Engineer Title Block with mandatory draft stamp:
   'STATUS: DRAFT - NOT FOR CONSTRUCTION. Not engineer-reviewed.'

Uses ezdxf library.
"""

from pathlib import Path
from typing import Dict, Any, Optional
import ezdxf
from ezdxf import colors


DRAFT_WATERMARK_TEXT = "STATUS: DRAFT - NOT FOR CONSTRUCTION. Not engineer-reviewed."


def create_slab_layers(doc: ezdxf.document.Drawing) -> None:
    """Configures professional CAD drafting layers with standard colors and lineweights."""
    layers = [
        {"name": "CONCRETE_OUTLINE", "color": colors.WHITE, "lineweight": 35},
        {"name": "REBAR_MAIN", "color": colors.RED, "lineweight": 50},
        {"name": "REBAR_DIST", "color": colors.BLUE, "lineweight": 35},
        {"name": "SUPPORTS", "color": colors.GRAY, "lineweight": 25},
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


def draw_slab_elevation_section(
    msp,
    origin_x: float,
    origin_y: float,
    span_mm: float,
    thickness_mm: float,
    support_width_mm: float,
    cover_mm: float,
    main_bar_dia_mm: float,
    main_spacing_mm: float,
    dist_bar_dia_mm: float,
    dist_spacing_mm: float,
    main_callout: str,
    dist_callout: str,
) -> None:
    """
    Draws detailed cross-sectional elevation of the slab supported on left and right walls/beams.
    """
    ox = origin_x
    oy = origin_y
    total_len = span_mm + 2.0 * support_width_mm

    # 1. Left & Right Support Walls / Beams (depth 300 mm below slab)
    support_depth = 300.0
    # Left support
    msp.add_lwpolyline(
        [
            (ox, oy - support_depth),
            (ox + support_width_mm, oy - support_depth),
            (ox + support_width_mm, oy),
            (ox, oy),
            (ox, oy - support_depth),
        ],
        dxfattribs={"layer": "SUPPORTS"},
    )
    # Right support
    rx = ox + support_width_mm + span_mm
    msp.add_lwpolyline(
        [
            (rx, oy - support_depth),
            (rx + support_width_mm, oy - support_depth),
            (rx + support_width_mm, oy),
            (rx, oy),
            (rx, oy - support_depth),
        ],
        dxfattribs={"layer": "SUPPORTS"},
    )

    # 2. Slab Concrete Outline
    slab_pts = [
        (ox, oy),
        (ox + total_len, oy),
        (ox + total_len, oy + thickness_mm),
        (ox, oy + thickness_mm),
        (ox, oy),
    ]
    msp.add_lwpolyline(slab_pts, dxfattribs={"layer": "CONCRETE_OUTLINE"})

    # 3. Main Bottom Rebar (Continuous rod running through slab into supports)
    rebar_y = oy + cover_mm + (main_bar_dia_mm / 2.0)
    left_rebar_x = ox + cover_mm
    right_rebar_x = ox + total_len - cover_mm

    msp.add_line(
        (left_rebar_x, rebar_y),
        (right_rebar_x, rebar_y),
        dxfattribs={"layer": "REBAR_MAIN"},
    )
    # 90-degree standard end anchor bends up into support
    anchor_y = min(oy + thickness_mm - cover_mm, rebar_y + 100.0)
    msp.add_line(
        (left_rebar_x, rebar_y),
        (left_rebar_x, anchor_y),
        dxfattribs={"layer": "REBAR_MAIN"},
    )
    msp.add_line(
        (right_rebar_x, rebar_y),
        (right_rebar_x, anchor_y),
        dxfattribs={"layer": "REBAR_MAIN"},
    )

    # 4. Transverse / Distribution Bars (represented as circles resting on top of main rebar)
    dist_bar_y = rebar_y + (main_bar_dia_mm / 2.0) + (dist_bar_dia_mm / 2.0)
    current_x = ox + support_width_mm + 50.0
    end_x = ox + support_width_mm + span_mm - 50.0

    while current_x <= end_x:
        msp.add_circle(
            (current_x, dist_bar_y),
            radius=dist_bar_dia_mm / 2.0,
            dxfattribs={"layer": "REBAR_DIST"},
        )
        current_x += dist_spacing_mm

    # 5. Dimensions
    # Span dimension
    dim_y = oy - 80.0
    msp.add_line(
        (ox + support_width_mm, dim_y),
        (ox + support_width_mm + span_mm, dim_y),
        dxfattribs={"layer": "DIMENSIONS"},
    )
    msp.add_line((ox + support_width_mm, dim_y - 15), (ox + support_width_mm, dim_y + 15), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_line((ox + support_width_mm + span_mm, dim_y - 15), (ox + support_width_mm + span_mm, dim_y + 15), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_text(
        f"CLEAR SPAN Lx = {int(span_mm)} mm",
        height=25.0,
        dxfattribs={"layer": "DIMENSIONS"},
    ).set_placement((ox + support_width_mm + (span_mm / 2.0) - 150.0, dim_y - 35.0))

    # Thickness dimension
    dim_x = ox + total_len + 60.0
    msp.add_line((dim_x, oy), (dim_x, oy + thickness_mm), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_line((dim_x - 15, oy), (dim_x + 15, oy), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_line((dim_x - 15, oy + thickness_mm), (dim_x + 15, oy + thickness_mm), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_text(
        f"D = {int(thickness_mm)} mm",
        height=25.0,
        dxfattribs={"layer": "DIMENSIONS"},
    ).set_placement((dim_x + 25.0, oy + (thickness_mm / 2.0) - 10.0))

    # 6. Rebar Callout Leaders & Labels
    # Main rebar label
    msp.add_line(
        (ox + support_width_mm + (span_mm / 3.0), rebar_y),
        (ox + support_width_mm + (span_mm / 3.0) - 80.0, oy - 180.0),
        dxfattribs={"layer": "TEXT_ANNOTATIONS"},
    )
    msp.add_text(
        f"MAIN BARS: {main_callout}",
        height=28.0,
        dxfattribs={"layer": "TEXT_ANNOTATIONS"},
    ).set_placement((ox + support_width_mm + (span_mm / 3.0) - 250.0, oy - 220.0))

    # Distribution rebar label
    sample_dist_x = ox + support_width_mm + 50.0 + dist_spacing_mm
    msp.add_line(
        (sample_dist_x, dist_bar_y),
        (sample_dist_x + 100.0, oy + thickness_mm + 80.0),
        dxfattribs={"layer": "TEXT_ANNOTATIONS"},
    )
    msp.add_text(
        f"DISTRIBUTION BARS: {dist_callout}",
        height=28.0,
        dxfattribs={"layer": "TEXT_ANNOTATIONS"},
    ).set_placement((sample_dist_x + 110.0, oy + thickness_mm + 75.0))

    # Title label
    msp.add_text(
        "CROSS-SECTION ELEVATION THROUGH SPAN (1:20)",
        height=32.0,
        dxfattribs={"layer": "TEXT_ANNOTATIONS"},
    ).set_placement((ox + (total_len / 2.0) - 250.0, oy - 280.0))


def draw_slab_plan_view(
    msp,
    origin_x: float,
    origin_y: float,
    lx_mm: float,
    ly_mm: float,
    main_callout: str,
    dist_callout: str,
    slab_type: str,
) -> None:
    """Draws plan view layout showing the slab panel, span directions, and grid markings."""
    ox = origin_x
    oy = origin_y

    # Panel boundary
    panel_pts = [
        (ox, oy),
        (ox + lx_mm, oy),
        (ox + lx_mm, oy + ly_mm),
        (ox, oy + ly_mm),
        (ox, oy),
    ]
    msp.add_lwpolyline(panel_pts, dxfattribs={"layer": "CONCRETE_OUTLINE"})

    # Span arrows
    # Lx direction (shorter span)
    arrow_y = oy + (ly_mm / 2.0)
    msp.add_line((ox + 50.0, arrow_y), (ox + lx_mm - 50.0, arrow_y), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_text(
        f"Lx = {int(lx_mm)} mm (Main Span)",
        height=30.0,
        dxfattribs={"layer": "DIMENSIONS"},
    ).set_placement((ox + (lx_mm / 2.0) - 150.0, arrow_y + 15.0))

    # Ly direction (longer span)
    arrow_x = ox + (lx_mm / 2.0)
    msp.add_line((arrow_x, oy + 50.0), (arrow_x, oy + ly_mm - 50.0), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_text(
        f"Ly = {int(ly_mm)} mm",
        height=30.0,
        dxfattribs={"layer": "DIMENSIONS"},
    ).set_placement((arrow_x + 15.0, oy + (ly_mm / 2.0) - 100.0))

    # Reinforcement indications
    msp.add_text(
        f"TYPE: {slab_type.upper().replace('_', '-')} SLAB",
        height=35.0,
        dxfattribs={"layer": "TEXT_ANNOTATIONS"},
    ).set_placement((ox + 50.0, oy + ly_mm - 100.0))

    msp.add_text(
        f"BOTTOM MAIN: {main_callout}",
        height=28.0,
        dxfattribs={"layer": "TEXT_ANNOTATIONS"},
    ).set_placement((ox + 50.0, oy + ly_mm - 160.0))

    msp.add_text(
        f"TRANSVERSE: {dist_callout}",
        height=28.0,
        dxfattribs={"layer": "TEXT_ANNOTATIONS"},
    ).set_placement((ox + 50.0, oy + ly_mm - 210.0))

    # Plan title
    msp.add_text(
        "SLAB REINFORCEMENT PLAN VIEW (1:50)",
        height=32.0,
        dxfattribs={"layer": "TEXT_ANNOTATIONS"},
    ).set_placement((ox + (lx_mm / 2.0) - 220.0, oy - 60.0))


def draw_slab_title_block(
    msp,
    origin_x: float,
    origin_y: float,
    width: float = 800.0,
    height: float = 240.0,
    project_title: str = "IS 456 RC SLAB DESIGN",
    slab_details: str = "3.00m x 4.50m x 125mm One-Way Slab",
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

    # Dividing lines
    msp.add_line((ox, oy + 160.0), (ox + width, oy + 160.0), dxfattribs={"layer": "TITLE_BLOCK"})
    msp.add_line((ox, oy + 80.0), (ox + width, oy + 80.0), dxfattribs={"layer": "TITLE_BLOCK"})

    # Text
    msp.add_text(project_title, height=22.0, dxfattribs={"layer": "TEXT_ANNOTATIONS"}).set_placement((ox + 20.0, oy + 185.0))
    msp.add_text(slab_details, height=18.0, dxfattribs={"layer": "TEXT_ANNOTATIONS"}).set_placement((ox + 20.0, oy + 115.0))
    msp.add_text(
        "CODE: IS 456:2000 | UNITS: mm | COVER: 20mm | GRADE: M25 / Fe500",
        height=14.0,
        dxfattribs={"layer": "TEXT_ANNOTATIONS"},
    ).set_placement((ox + 20.0, oy + 95.0))

    # Watermark Draft Stamp
    msp.add_text(
        DRAFT_WATERMARK_TEXT,
        height=16.0,
        dxfattribs={"layer": "WATERMARK"},
    ).set_placement((ox + 20.0, oy + 35.0))


def export_slab_dxf(
    design: Dict[str, Any],
    output_path: Optional[str] = None,
    output_filename: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Exports complete AutoCAD DXF file for a designed RC slab.
    Supports either output_path or output_filename keyword arguments.
    """
    dest_path = output_path or output_filename or kwargs.get("filepath") or "slab_design.dxf"
    out_file = Path(dest_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    doc = ezdxf.new("R2010")
    doc.units = 4  # Millimetres
    doc.header["$INSUNITS"] = 4
    create_slab_layers(doc)
    msp = doc.modelspace()

    geom = design["geometry"]
    classif = design["classification"]
    flex = design["flexure"]
    main_reb = flex["main_rebar_x"]
    trans_reb = flex["transverse_reinforcement"]["rebar"]

    lx_mm = classif["shorter_span_Lx_m"] * 1000.0
    ly_mm = classif["longer_span_Ly_m"] * 1000.0
    thickness_mm = geom["overall_depth_D_mm"]
    cover_mm = geom["nominal_cover_mm"]
    support_width_mm = 230.0

    # 1. Cross-Section Elevation View
    draw_slab_elevation_section(
        msp=msp,
        origin_x=0.0,
        origin_y=0.0,
        span_mm=lx_mm,
        thickness_mm=thickness_mm,
        support_width_mm=support_width_mm,
        cover_mm=cover_mm,
        main_bar_dia_mm=float(main_reb["bar_dia_mm"]),
        main_spacing_mm=float(main_reb["spacing_mm"]),
        dist_bar_dia_mm=float(trans_reb["bar_dia_mm"]),
        dist_spacing_mm=float(trans_reb["spacing_mm"]),
        main_callout=main_reb["callout"],
        dist_callout=trans_reb["callout"],
    )

    # 2. Plan View (positioned to the right or above)
    plan_ox = lx_mm + 2.0 * support_width_mm + 600.0
    plan_oy = 0.0
    draw_slab_plan_view(
        msp=msp,
        origin_x=plan_ox,
        origin_y=plan_oy,
        lx_mm=lx_mm,
        ly_mm=ly_mm,
        main_callout=main_reb["callout"],
        dist_callout=trans_reb["callout"],
        slab_type=classif["slab_type"],
    )

    # 3. Title Block
    tb_ox = 0.0
    tb_oy = -600.0
    summary_txt = f"{classif['shorter_span_Lx_m']:.2f}m x {classif['longer_span_Ly_m']:.2f}m x {int(thickness_mm)}mm ({classif['slab_type'].upper().replace('_', '-')})"
    draw_slab_title_block(
        msp=msp,
        origin_x=tb_ox,
        origin_y=tb_oy,
        width=1100.0,
        height=240.0,
        project_title="IS 456 RC SLAB REINFORCEMENT DESIGN",
        slab_details=summary_txt,
    )

    doc.saveas(str(out_file))

    return {
        "status": "success",
        "dxf_path": str(out_file.resolve()),
        "slab_type": classif["slab_type"],
        "dimensions": f"{int(lx_mm)}x{int(ly_mm)} mm, D={int(thickness_mm)} mm",
        "main_reinforcement": main_reb["callout"],
        "transverse_reinforcement": trans_reb["callout"],
        "approval_status": "DRAFT - NOT FOR CONSTRUCTION",
    }
