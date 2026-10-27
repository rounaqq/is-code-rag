"""
2D CAD DXF Drafting Engine for IS 456:2000 Reinforced Concrete Columns.
Generates compliant vector DXF drawings including:
  1. Column Cross-Section (outer boundary, longitudinal bars, outer tie with hooks, dimensions)
  2. Longitudinal Elevation (vertical height, main bars, horizontal ties at pitch)
  3. Standard Title Block with draft status:
     "STATUS: DRAFT - NOT FOR CONSTRUCTION. Not engineer-reviewed."
Zero proprietary software required; uses open standard ezdxf.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List
import ezdxf
from ezdxf import colors


def export_column_dxf(
    design: Dict[str, Any],
    output_path: str,
) -> Dict[str, Any]:
    """
    Exports a 2D AutoCAD DXF drawing for an IS 456 RC Column design.
    """
    b = float(design.get("width_mm", 400))
    D = float(design.get("depth_mm", 400))
    L = float(design.get("length_m", 3.0)) * 1000.0  # mm
    cover = float(design.get("cover_mm", 40))

    rebar = design.get("rebar_selected", {})
    bar_count = int(rebar.get("bar_count", 4))
    bar_dia = float(rebar.get("bar_diameter_mm", 16))
    bar_callout = rebar.get("callout", f"{bar_count}-T{int(bar_dia)}")

    ties = design.get("lateral_ties", {})
    tie_dia = float(ties.get("tie_diameter_mm", 8))
    tie_pitch = float(ties.get("tie_pitch_mm", 250))
    tie_callout = ties.get("callout", f"T{int(tie_dia)} @ {int(tie_pitch)} c/c")

    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    # Setup standard layers
    layers = [
        ("CONCRETE", colors.WHITE, "CONTINUOUS"),
        ("REBAR", colors.RED, "CONTINUOUS"),
        ("TIES", colors.CYAN, "CONTINUOUS"),
        ("DIMENSIONS", colors.GREEN, "CONTINUOUS"),
        ("ANNOTATIONS", colors.YELLOW, "CONTINUOUS"),
        ("TITLE_BLOCK", colors.WHITE, "CONTINUOUS"),
    ]
    for name, color, linetype in layers:
        if name not in doc.layers:
            doc.layers.add(name=name, color=color, linetype=linetype)

    # =========================================================================
    # 1. CROSS-SECTION (PLAN VIEW) at (X=0, Y=0)
    # =========================================================================
    # Concrete Outer Boundary
    msp.add_lwpolyline([(0, 0), (b, 0), (b, D), (0, D), (0, 0)], dxfattribs={"layer": "CONCRETE"})

    # Outer Lateral Tie Link (offset by cover)
    tie_x0 = cover
    tie_y0 = cover
    tie_x1 = b - cover
    tie_y1 = D - cover
    msp.add_lwpolyline(
        [(tie_x0, tie_y0), (tie_x1, tie_y0), (tie_x1, tie_y1), (tie_x0, tie_y1), (tie_x0, tie_y0)],
        dxfattribs={"layer": "TIES"},
    )

    # 135-degree seismic hook representation
    hook_len = max(10.0 * tie_dia, 75.0)
    msp.add_line((tie_x0, tie_y0), (tie_x0 + hook_len * 0.707, tie_y0 + hook_len * 0.707), dxfattribs={"layer": "TIES"})

    # Longitudinal Bar Positions
    bar_radius = bar_dia / 2.0
    core_x0 = tie_x0 + tie_dia + bar_radius
    core_y0 = tie_y0 + tie_dia + bar_radius
    core_x1 = tie_x1 - tie_dia - bar_radius
    core_y1 = tie_y1 - tie_dia - bar_radius

    bar_coords: List[Tuple[float, float]] = []

    # 4 Corner Bars
    bar_coords.append((core_x0, core_y0))
    bar_coords.append((core_x1, core_y0))
    bar_coords.append((core_x1, core_y1))
    bar_coords.append((core_x0, core_y1))

    # Intermediate bars
    if bar_count == 6:
        # 2 bars on faces D (along Y)
        mid_y = (core_y0 + core_y1) / 2.0
        bar_coords.append((core_x0, mid_y))
        bar_coords.append((core_x1, mid_y))
    elif bar_count == 8:
        # 2 bars on faces D + 2 on faces b
        mid_x = (core_x0 + core_x1) / 2.0
        mid_y = (core_y0 + core_y1) / 2.0
        bar_coords.append((core_x0, mid_y))
        bar_coords.append((core_x1, mid_y))
        bar_coords.append((mid_x, core_y0))
        bar_coords.append((mid_x, core_y1))

    for bx, by in bar_coords:
        msp.add_circle((bx, by), radius=bar_radius, dxfattribs={"layer": "REBAR"})

    # Cross-Section Dimensions
    dim_offset = 60.0
    msp.add_line((0, -dim_offset), (b, -dim_offset), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_text(f"b = {int(b)} mm", dxfattribs={"layer": "DIMENSIONS", "height": 20}).set_placement(
        (b / 2.0 - 40, -dim_offset - 30)
    )

    msp.add_line((-dim_offset, 0), (-dim_offset, D), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_text(f"D = {int(D)} mm", dxfattribs={"layer": "DIMENSIONS", "height": 20, "rotation": 90}).set_placement(
        (-dim_offset - 30, D / 2.0 - 40)
    )

    # Cross-Section Titles & Notes
    msp.add_text("COLUMN CROSS-SECTION", dxfattribs={"layer": "ANNOTATIONS", "height": 25}).set_placement((0, D + 60))
    msp.add_text(f"Size: {int(b)} x {int(D)} mm | Cover: {int(cover)} mm", dxfattribs={"layer": "ANNOTATIONS", "height": 18}).set_placement((0, D + 30))
    msp.add_text(f"Main Rebar: {bar_callout}", dxfattribs={"layer": "ANNOTATIONS", "height": 18}).set_placement((0, -dim_offset - 70))
    msp.add_text(f"Lateral Ties: {tie_callout}", dxfattribs={"layer": "ANNOTATIONS", "height": 18}).set_placement((0, -dim_offset - 100))

    # =========================================================================
    # 2. LONGITUDINAL ELEVATION VIEW at (X = b + 300, Y = 0)
    # =========================================================================
    elev_x = b + 300.0
    elev_width = b
    elev_height = min(L, 3500.0)  # scale display height

    # Concrete Column Shaft
    msp.add_lwpolyline(
        [(elev_x, 0), (elev_x + elev_width, 0), (elev_x + elev_width, elev_height), (elev_x, elev_height), (elev_x, 0)],
        dxfattribs={"layer": "CONCRETE"},
    )

    # Vertical Main Bars
    rebar_x0 = elev_x + cover + tie_dia + bar_radius
    rebar_x1 = elev_x + elev_width - cover - tie_dia - bar_radius
    msp.add_line((rebar_x0, 0), (rebar_x0, elev_height), dxfattribs={"layer": "REBAR"})
    msp.add_line((rebar_x1, 0), (rebar_x1, elev_height), dxfattribs={"layer": "REBAR"})

    if bar_count >= 6:
        rebar_mid_x = (rebar_x0 + rebar_x1) / 2.0
        msp.add_line((rebar_mid_x, 0), (rebar_mid_x, elev_height), dxfattribs={"layer": "REBAR"})

    is_seismic = bool(
        design.get("is_seismic", False)
        or design.get("is_ductile", False)
        or str(design.get("seismic_zone", "")).upper() in ["III", "IV", "V"]
    )
    seismic_zone = str(design.get("seismic_zone", "IV")) if is_seismic else None

    # Calculate IS 13920 Confinement Parameters (Cl. 7.6.1)
    if is_seismic:
        lo = max(max(b, D), L / 6.0, 450.0)
        s_conf = min(min(b, D) / 4.0, 6.0 * bar_dia, 100.0)
        s_conf = max(s_conf, 65.0)  # min 65 mm pitch
        s_mid = min(tie_pitch, min(b, D) / 2.0, 300.0)
        tie_callout = f"Confining: T{int(tie_dia)} @ {int(s_conf)} c/c (lo={int(lo)}mm) | Mid: T{int(tie_dia)} @ {int(s_mid)} c/c"
    else:
        lo = 0.0
        s_conf = tie_pitch
        s_mid = tie_pitch

    # Horizontal Ties along Height
    tie_y_positions: List[float] = []
    if is_seismic and (2.0 * lo < elev_height):
        # Bottom confining zone: 0 to lo
        y = 50.0
        while y <= lo:
            tie_y_positions.append(y)
            y += s_conf

        # Middle intermediate zone: lo to (elev_height - lo)
        top_lo_start = elev_height - lo
        mid_y = lo + s_mid
        while mid_y < (top_lo_start - 20.0):
            tie_y_positions.append(mid_y)
            mid_y += s_mid

        # Top confining zone: (elev_height - lo) to elev_height
        y = top_lo_start
        while y <= (elev_height - 50.0):
            tie_y_positions.append(y)
            y += s_conf
    else:
        cur_y = 50.0
        while cur_y < (elev_height - 50.0):
            tie_y_positions.append(cur_y)
            cur_y += tie_pitch

    for ty in tie_y_positions:
        msp.add_line((elev_x + cover, ty), (elev_x + elev_width - cover, ty), dxfattribs={"layer": "TIES"})

    # Elevation Dimensions
    dim_elev_x = elev_x + elev_width + 50.0
    if is_seismic and (2.0 * lo < elev_height):
        # Bottom lo dimension
        msp.add_line((dim_elev_x, 0), (dim_elev_x, lo), dxfattribs={"layer": "DIMENSIONS"})
        msp.add_text(f"lo = {int(lo)} mm", dxfattribs={"layer": "DIMENSIONS", "height": 14, "rotation": 90}).set_placement((dim_elev_x + 18, lo / 2.0 - 25))
        # Top lo dimension
        top_lo_start = elev_height - lo
        msp.add_line((dim_elev_x, top_lo_start), (dim_elev_x, elev_height), dxfattribs={"layer": "DIMENSIONS"})
        msp.add_text(f"lo = {int(lo)} mm", dxfattribs={"layer": "DIMENSIONS", "height": 14, "rotation": 90}).set_placement((dim_elev_x + 18, top_lo_start + lo / 2.0 - 25))
        # Total height
        dim_total_x = dim_elev_x + 60.0
        msp.add_line((dim_total_x, 0), (dim_total_x, elev_height), dxfattribs={"layer": "DIMENSIONS"})
        msp.add_text(f"H = {int(L)} mm", dxfattribs={"layer": "DIMENSIONS", "height": 18, "rotation": 90}).set_placement((dim_total_x + 22, elev_height / 2.0 - 30))
    else:
        msp.add_line((dim_elev_x, 0), (dim_elev_x, elev_height), dxfattribs={"layer": "DIMENSIONS"})
        msp.add_text(f"H = {int(L)} mm", dxfattribs={"layer": "DIMENSIONS", "height": 18, "rotation": 90}).set_placement((dim_elev_x + 22, elev_height / 2.0 - 30))

    # Elevation Annotations
    msp.add_text("LONGITUDINAL ELEVATION", dxfattribs={"layer": "ANNOTATIONS", "height": 25}).set_placement((elev_x, elev_height + 60))
    msp.add_text(f"Clear Height: {int(L)} mm", dxfattribs={"layer": "ANNOTATIONS", "height": 18}).set_placement((elev_x, elev_height + 30))
    msp.add_text(f"Ties: {tie_callout}", dxfattribs={"layer": "ANNOTATIONS", "height": 16}).set_placement((elev_x, -dim_offset - 30))
    if is_seismic:
        msp.add_text(f"IS 13920 Cl. 7.6.1 Ductile Ties (Zone {seismic_zone or 'IV'})", dxfattribs={"layer": "ANNOTATIONS", "height": 15}).set_placement((elev_x, -dim_offset - 60))

    # =========================================================================
    # 3. TITLE BLOCK & COMPLIANCE NOTES
    # =========================================================================
    tb_x = 0
    tb_y = -350.0
    tb_w = elev_x + elev_width + 120.0
    tb_h = 160.0

    msp.add_lwpolyline(
        [(tb_x, tb_y), (tb_w, tb_y), (tb_w, tb_y + tb_h), (tb_x, tb_y + tb_h), (tb_x, tb_y)],
        dxfattribs={"layer": "TITLE_BLOCK"},
    )

    approval_status = design.get("approval_status", "STATUS: DRAFT - NOT FOR CONSTRUCTION. Not engineer-reviewed.")
    title_text = "IS 456 / IS 13920 SEISMIC RC COLUMN DESIGN" if is_seismic else "IS 456:2000 REINFORCED CONCRETE COLUMN DESIGN"
    msp.add_text(title_text, dxfattribs={"layer": "TITLE_BLOCK", "height": 22}).set_placement((tb_x + 20, tb_y + 120))
    msp.add_text(f"Section: {int(b)}x{int(D)} mm | Load Pu: {design.get('factored_axial_load_Pu_kN', 'N/A')} kN | Capacity: {design.get('axial_capacity_Pu_kN', 'N/A')} kN", dxfattribs={"layer": "TITLE_BLOCK", "height": 16}).set_placement((tb_x + 20, tb_y + 90))
    mat_note = f"Materials: Concrete M{int(design.get('fck', 25))} | Steel Fe{int(design.get('fy', 500))} | Exposure: {design.get('exposure', 'Moderate')}"
    if is_seismic:
        mat_note += f" | Seismic Zone: {seismic_zone or 'IV'}"
    msp.add_text(mat_note, dxfattribs={"layer": "TITLE_BLOCK", "height": 16}).set_placement((tb_x + 20, tb_y + 60))
    msp.add_text(approval_status, dxfattribs={"layer": "TITLE_BLOCK", "height": 18}).set_placement((tb_x + 20, tb_y + 25))

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(out_file))

    return {
        "status": "success",
        "dxf_path": str(out_file),
        "section_dimensions": f"{int(b)}x{int(D)} mm",
        "rebar": bar_callout,
        "ties": tie_callout,
        "approval_status": approval_status,
    }
