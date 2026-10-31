"""
IS 456:2000 2D CAD Drawing Generator using ezdxf.
Maps validated structural beam design parameters to compliant 2D CAD entities:
  1. Cross-Section View (Section A-A): Dimensions, cover, longitudinal bars, closed stirrup tie.
  2. Longitudinal Elevation View: Span, support bearings, rebar bends, stirrup distribution.
  3. IS 456 Compliance Annotations: Code clause callouts (Table 16, Table 20, Cl. 26.5.1, Annex G).
  4. Standard Title Block: Project metadata, scale, and general engineering notes.
Does NOT import, read, print, or quote .env or any secret keys.
"""

import math
import textwrap
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import ezdxf
from ezdxf.document import Drawing
from ezdxf.layouts import Modelspace

from src.validation.is456_checks import nominal_cover
from src.generation.design_validation import validate_design


# Layer configuration with standard CAD colors and lineweights
LAYERS_CONFIG = {
    "OUTLINE": {"color": 7, "lineweight": 35},       # White/Black - Concrete outlines
    "REBAR_MAIN": {"color": 1, "lineweight": 50},     # Red - Tension reinforcement
    "REBAR_TOP": {"color": 3, "lineweight": 35},      # Green - Compression / hanger bars
    "STIRRUPS": {"color": 4, "lineweight": 25},       # Cyan - Shear stirrup ties
    "DIMENSIONS": {"color": 2, "lineweight": 18},     # Yellow - Dimension lines and text
    "ANNOTATIONS": {"color": 6, "lineweight": 25},    # Magenta - Rebar callouts and text
    "TITLE_BLOCK": {"color": 5, "lineweight": 25},    # Blue - Border and title block
    "HATCH": {"color": 8, "lineweight": 13},          # Dark Gray - Concrete hatching/supports
}


def setup_layers(doc: Drawing) -> None:
    """Configures CAD layers with appropriate colors and lineweights."""
    for name, props in LAYERS_CONFIG.items():
        if name not in doc.layers:
            doc.layers.add(
                name=name,
                color=props["color"],
                lineweight=props["lineweight"],
            )


def draw_dimension_horizontal(
    msp: Modelspace,
    x1: float,
    x2: float,
    y: float,
    text: str,
    offset: float = 40.0,
    tick_size: float = 10.0,
    text_height: float = 15.0,
) -> None:
    """Draws a horizontal dimension line with extension lines, end ticks, and label."""
    dim_y = y - offset
    # Extension lines
    msp.add_line((x1, y), (x1, dim_y - tick_size), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_line((x2, y), (x2, dim_y - tick_size), dxfattribs={"layer": "DIMENSIONS"})
    # Dimension line
    msp.add_line((x1, dim_y), (x2, dim_y), dxfattribs={"layer": "DIMENSIONS"})
    # 45-degree tick marks
    msp.add_line((x1 - tick_size, dim_y - tick_size), (x1 + tick_size, dim_y + tick_size), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_line((x2 - tick_size, dim_y - tick_size), (x2 + tick_size, dim_y + tick_size), dxfattribs={"layer": "DIMENSIONS"})
    # Text centered above dimension line
    mid_x = (x1 + x2) / 2.0
    text_entity = msp.add_text(
        text,
        dxfattribs={"layer": "DIMENSIONS", "height": text_height},
    )
    text_entity.set_placement((mid_x, dim_y + 4.0), align=ezdxf.enums.TextEntityAlignment.BOTTOM_CENTER)


def draw_dimension_vertical(
    msp: Modelspace,
    y1: float,
    y2: float,
    x: float,
    text: str,
    offset: float = 40.0,
    tick_size: float = 10.0,
    text_height: float = 15.0,
) -> None:
    """Draws a vertical dimension line with extension lines, end ticks, and label."""
    dim_x = x + offset
    # Extension lines
    msp.add_line((x, y1), (dim_x + tick_size, y1), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_line((x, y2), (dim_x + tick_size, y2), dxfattribs={"layer": "DIMENSIONS"})
    # Dimension line
    msp.add_line((dim_x, y1), (dim_x, y2), dxfattribs={"layer": "DIMENSIONS"})
    # 45-degree tick marks
    msp.add_line((dim_x - tick_size, y1 - tick_size), (dim_x + tick_size, y1 + tick_size), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_line((dim_x - tick_size, y2 - tick_size), (dim_x + tick_size, y2 + tick_size), dxfattribs={"layer": "DIMENSIONS"})
    # Text centered and rotated 90 degrees
    mid_y = (y1 + y2) / 2.0
    text_entity = msp.add_text(
        text,
        dxfattribs={"layer": "DIMENSIONS", "height": text_height, "rotation": 90.0},
    )
    text_entity.set_placement((dim_x + 6.0, mid_y), align=ezdxf.enums.TextEntityAlignment.BOTTOM_CENTER)


def draw_cross_section(
    msp: Modelspace,
    origin: Tuple[float, float],
    b: float,
    D: float,
    d: float,
    cover_mm: float,
    main_bar_dia: float,
    main_bar_count: int,
    comp_bar_dia: float,
    comp_bar_count: int,
    stirrup_dia: float,
    stirrup_spacing: float,
    is_seismic: bool = False,
) -> None:
    """Draws the transverse cross-section of the RC beam with all detailing callouts."""
    ox, oy = origin

    # 1. Concrete Outer Rectangle
    msp.add_lwpolyline(
        [(ox, oy), (ox + b, oy), (ox + b, oy + D), (ox, oy + D), (ox, oy)],
        close=True,
        dxfattribs={"layer": "OUTLINE"},
    )

    # 2. Closed Stirrup Outer Perimeter
    stirrup_x1 = ox + cover_mm
    stirrup_y1 = oy + cover_mm
    stirrup_x2 = ox + b - cover_mm
    stirrup_y2 = oy + D - cover_mm

    msp.add_lwpolyline(
        [
            (stirrup_x1, stirrup_y1),
            (stirrup_x2, stirrup_y1),
            (stirrup_x2, stirrup_y2),
            (stirrup_x1, stirrup_y2),
            (stirrup_x1, stirrup_y1),
        ],
        close=True,
        dxfattribs={"layer": "STIRRUPS"},
    )

    # 3. Bottom Tension Bars
    # Center y = cover + stirrup_dia + main_bar_dia / 2
    bot_y = oy + cover_mm + stirrup_dia + (main_bar_dia / 2.0)
    left_x = ox + cover_mm + stirrup_dia + (main_bar_dia / 2.0)
    right_x = ox + b - cover_mm - stirrup_dia - (main_bar_dia / 2.0)

    if main_bar_count > 1:
        step_x = (right_x - left_x) / (main_bar_count - 1)
        bot_bar_centers = [left_x + i * step_x for i in range(main_bar_count)]
    else:
        bot_bar_centers = [(left_x + right_x) / 2.0]

    for cx in bot_bar_centers:
        msp.add_circle((cx, bot_y), radius=main_bar_dia / 2.0, dxfattribs={"layer": "REBAR_MAIN"})
        # Draw solid fill marker inside bar
        msp.add_circle((cx, bot_y), radius=main_bar_dia / 4.0, dxfattribs={"layer": "REBAR_MAIN"})

    # 4. Top Compression / Hanger Bars
    top_y = oy + D - cover_mm - stirrup_dia - (comp_bar_dia / 2.0)
    top_left_x = ox + cover_mm + stirrup_dia + (comp_bar_dia / 2.0)
    top_right_x = ox + b - cover_mm - stirrup_dia - (comp_bar_dia / 2.0)

    if comp_bar_count > 1:
        step_top_x = (top_right_x - top_left_x) / (comp_bar_count - 1)
        top_bar_centers = [top_left_x + i * step_top_x for i in range(comp_bar_count)]
    else:
        top_bar_centers = [(top_left_x + top_right_x) / 2.0]

    for cx in top_bar_centers:
        msp.add_circle((cx, top_y), radius=comp_bar_dia / 2.0, dxfattribs={"layer": "REBAR_TOP"})
        msp.add_circle((cx, top_y), radius=comp_bar_dia / 4.0, dxfattribs={"layer": "REBAR_TOP"})

    # 5. Dimensions
    # Calculate effective depth from compression face to centroid of bottom bars as drawn
    d_drawn = D - (cover_mm + stirrup_dia + (main_bar_dia / 2.0))
    if abs(d_drawn - d) > 1e-4:
        print(
            f"Effective depth 'd' check:\n"
            f"  - Design d: {d} mm\n"
            f"  - Drawn d (compression face to bottom bar centroid): {d_drawn} mm"
        )

    draw_dimension_horizontal(msp, ox, ox + b, oy, f"b = {int(round(b))} mm", offset=50.0)
    draw_dimension_vertical(msp, oy, oy + D, ox + b, f"D = {int(round(D))} mm", offset=50.0)
    draw_dimension_vertical(msp, bot_y, oy + D, ox + b, f"d = {int(round(d_drawn))} mm", offset=110.0)

    # 6. Annotations & Callouts with leader lines
    # Section Title
    title = msp.add_text("SECTION A-A", dxfattribs={"layer": "ANNOTATIONS", "height": 22.0})
    title.set_placement((ox + b / 2.0, oy - 100.0), align=ezdxf.enums.TextEntityAlignment.TOP_CENTER)

    # Callout: Bottom tension bars
    lbl_bot = f"{main_bar_count}-T{int(round(main_bar_dia))} Bottom Bars (IS 456 Cl. 26.5.1.1)"
    msp.add_line((bot_bar_centers[0], bot_y), (ox - 80.0, bot_y - 40.0), dxfattribs={"layer": "ANNOTATIONS"})
    msp.add_line((ox - 80.0, bot_y - 40.0), (ox - 140.0, bot_y - 40.0), dxfattribs={"layer": "ANNOTATIONS"})
    txt_bot = msp.add_text(lbl_bot, dxfattribs={"layer": "ANNOTATIONS", "height": 13.0})
    txt_bot.set_placement((ox - 145.0, bot_y - 36.0), align=ezdxf.enums.TextEntityAlignment.BOTTOM_RIGHT)

    # Callout: Top hanger bars
    lbl_top = f"{comp_bar_count}-T{int(round(comp_bar_dia))} Hanger Bars (Top)"
    msp.add_line((top_bar_centers[0], top_y), (ox - 80.0, top_y + 40.0), dxfattribs={"layer": "ANNOTATIONS"})
    msp.add_line((ox - 80.0, top_y + 40.0), (ox - 140.0, top_y + 40.0), dxfattribs={"layer": "ANNOTATIONS"})
    txt_top = msp.add_text(lbl_top, dxfattribs={"layer": "ANNOTATIONS", "height": 13.0})
    txt_top.set_placement((ox - 145.0, top_y + 44.0), align=ezdxf.enums.TextEntityAlignment.BOTTOM_RIGHT)

    # Callout: Stirrups
    lbl_str = f"2L-T{int(round(stirrup_dia))} @ {int(round(stirrup_spacing))} c/c (IS 456 Cl. 26.5.1.5, 26.5.1.6)"
    mid_str_y = (stirrup_y1 + stirrup_y2) / 2.0
    msp.add_line((stirrup_x1, mid_str_y), (ox - 60.0, mid_str_y), dxfattribs={"layer": "ANNOTATIONS"})
    txt_str = msp.add_text(lbl_str, dxfattribs={"layer": "ANNOTATIONS", "height": 13.0})
    txt_str.set_placement((ox - 65.0, mid_str_y + 4.0), align=ezdxf.enums.TextEntityAlignment.BOTTOM_RIGHT)

    # Callout: Nominal cover
    lbl_cov = f"Clear Cover: {int(round(cover_mm))} mm (Table 16)"
    txt_cov = msp.add_text(lbl_cov, dxfattribs={"layer": "ANNOTATIONS", "height": 12.0})
    txt_cov.set_placement((ox + b / 2.0, oy + 4.0), align=ezdxf.enums.TextEntityAlignment.BOTTOM_CENTER)

    # 135-degree Seismic Hook Details (IS 13920:2016 Cl. 5.2)
    if is_seismic:
        hook_proj = max(10.0 * stirrup_dia, 65.0) * 0.7071
        msp.add_line((stirrup_x1, stirrup_y2), (stirrup_x1 + hook_proj, stirrup_y2 - hook_proj), dxfattribs={"layer": "STIRRUPS"})
        msp.add_line((stirrup_x2, stirrup_y2), (stirrup_x2 - hook_proj, stirrup_y2 - hook_proj), dxfattribs={"layer": "STIRRUPS"})
        txt_hook = msp.add_text("135° Seismic Hook ext >= 10db (IS 13920 Cl. 5.2)", dxfattribs={"layer": "ANNOTATIONS", "height": 11.0})
        txt_hook.set_placement((ox + b / 2.0, oy + D + 15.0), align=ezdxf.enums.TextEntityAlignment.BOTTOM_CENTER)


def compute_symmetric_stirrup_positions(
    span_mm: float,
    support_width_mm: float,
    stirrup_spacing: float,
    ox: float = 0.0,
) -> List[float]:
    """
    Computes stirrup positions along the beam symmetric about mid-span.
    Requirements:
      - First stirrup is 50 mm from each support face.
      - Spacing equal to design spacing.
      - No gap between consecutive stirrups larger than design spacing.
      - Symmetrically placed about mid-span.
    """
    if stirrup_spacing <= 0:
        raise ValueError("Stirrup spacing must be strictly positive.")

    x_left_face = ox + support_width_mm
    x_right_face = x_left_face + span_mm
    x_first = x_left_face + 50.0
    x_last = x_right_face - 50.0
    mid_x = (x_first + x_last) / 2.0

    if x_first >= x_last:
        return [round(mid_x, 6)]

    half_dist = mid_x - x_first
    s = float(stirrup_spacing)
    k = int(half_dist // s)
    rem = half_dist - (k * s)

    left_positions = [round(x_first + i * s, 6) for i in range(k + 1)]
    right_positions = [round(x_last - i * s, 6) for i in range(k + 1)]

    gap = 2.0 * rem

    if gap <= 1e-4:
        positions = left_positions[:-1] + [round(mid_x, 6)] + list(reversed(right_positions[:-1]))
    elif gap <= s + 1e-4:
        positions = left_positions + list(reversed(right_positions))
    else:
        positions = left_positions + [round(mid_x, 6)] + list(reversed(right_positions))

    return positions


def compute_seismic_stirrup_positions(
    span_mm: float,
    support_width_mm: float,
    d: float,
    s_conf: float = 100.0,
    s_mid: float = 150.0,
    ox: float = 0.0,
) -> Tuple[List[float], float, float]:
    """
    Computes stirrup positions per IS 13920:2016 Cl. 6.3.3:
    1. Support Confinement Zone: Length = 2 * d from support face.
       First stirrup starts at <= 50 mm from column face.
       Spacing s_conf <= min(d/4, 8*db_min, 100 mm).
    2. Midspan Zone: Remaining central span.
       Spacing s_mid <= min(d/2, 300 mm).
    Returns:
        (sorted_unique_positions, left_zone_end_x, right_zone_start_x)
    """
    x_left_face = ox + support_width_mm
    x_right_face = x_left_face + span_mm
    L_conf = round(2.0 * d, 1)

    if 2.0 * L_conf >= span_mm:
        # Short beam: entire span is confinement zone
        pos = compute_symmetric_stirrup_positions(
            span_mm=span_mm,
            support_width_mm=support_width_mm,
            stirrup_spacing=s_conf,
            ox=ox,
        )
        return pos, x_right_face, x_left_face

    # Left confinement zone
    x_first = x_left_face + 50.0
    x_left_conf_end = x_left_face + L_conf
    left_positions = []
    curr = x_first
    while curr <= (x_left_conf_end + 1e-4):
        left_positions.append(round(curr, 2))
        curr += s_conf

    # Right confinement zone (symmetric)
    x_last = x_right_face - 50.0
    x_right_conf_start = x_right_face - L_conf
    right_positions = []
    curr = x_last
    while curr >= (x_right_conf_start - 1e-4):
        right_positions.append(round(curr, 2))
        curr -= s_conf
    right_positions.reverse()

    # Midspan zone between last left stirrup and first right stirrup
    mid_start = left_positions[-1]
    mid_end = right_positions[0]
    mid_dist = mid_end - mid_start
    mid_positions = []

    if mid_dist > s_mid:
        k = int(mid_dist // s_mid)
        actual_spacing = mid_dist / (k + 1)
        for i in range(1, k + 1):
            mid_positions.append(round(mid_start + i * actual_spacing, 2))

    all_positions = sorted(list(set(left_positions + mid_positions + right_positions)))
    return all_positions, x_left_conf_end, x_right_conf_start


def draw_longitudinal_elevation(
    msp: Modelspace,
    origin: Tuple[float, float],
    span_mm: float,
    b: float,
    D: float,
    cover_mm: float,
    main_bar_dia: float,
    main_bar_count: int,
    comp_bar_dia: float,
    comp_bar_count: int,
    stirrup_dia: float,
    stirrup_spacing: float,
    support_width_mm: float = 300.0,
    d: Optional[float] = None,
    is_seismic: bool = False,
    seismic_zone: Optional[str] = None,
) -> None:
    """Draws longitudinal elevation view showing beam span, supports, rebar bends, and stirrups."""
    ox, oy = origin
    total_length = span_mm + 2.0 * support_width_mm

    # 1. Bearing Supports (Left and Right columns/walls)
    support_depth = 250.0
    # Left support
    msp.add_lwpolyline(
        [
            (ox, oy - support_depth),
            (ox + support_width_mm, oy - support_depth),
            (ox + support_width_mm, oy),
            (ox, oy),
            (ox, oy - support_depth),
        ],
        close=True,
        dxfattribs={"layer": "HATCH"},
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
        close=True,
        dxfattribs={"layer": "HATCH"},
    )

    # 2. Concrete Outline of Beam
    msp.add_lwpolyline(
        [
            (ox, oy),
            (ox + total_length, oy),
            (ox + total_length, oy + D),
            (ox, oy + D),
            (ox, oy),
        ],
        close=True,
        dxfattribs={"layer": "OUTLINE"},
    )

    # 3. Bottom Tension Bars with 90-degree development hooks at supports (IS 456 Cl. 26.2)
    bot_y = oy + cover_mm + stirrup_dia + (main_bar_dia / 2.0)
    hook_height = min(D / 2.0, 150.0)
    bar_start_x = ox + cover_mm
    bar_end_x = ox + total_length - cover_mm

    # Bottom rebar polyline with end bends
    msp.add_lwpolyline(
        [
            (bar_start_x, bot_y + hook_height),
            (bar_start_x, bot_y),
            (bar_end_x, bot_y),
            (bar_end_x, bot_y + hook_height),
        ],
        dxfattribs={"layer": "REBAR_MAIN"},
    )

    # 4. Top Compression / Hanger Bars
    top_y = oy + D - cover_mm - stirrup_dia - (comp_bar_dia / 2.0)
    msp.add_lwpolyline(
        [
            (bar_start_x, top_y - hook_height),
            (bar_start_x, top_y),
            (bar_end_x, top_y),
            (bar_end_x, top_y - hook_height),
        ],
        dxfattribs={"layer": "REBAR_TOP"},
    )

    # 5. Stirrups distributed across the clear span
    stirrup_bot_y = oy + cover_mm
    stirrup_top_y = oy + D - cover_mm
    effective_d = d or (D - cover_mm - stirrup_dia - (main_bar_dia / 2.0))

    if is_seismic:
        s_conf = min(round(effective_d / 4.0, 1), round(8.0 * main_bar_dia, 1), 100.0)
        s_mid = min(stirrup_spacing, round(effective_d / 2.0, 1), 300.0)
        stirrup_positions, left_conf_end, right_conf_start = compute_seismic_stirrup_positions(
            span_mm=span_mm,
            support_width_mm=support_width_mm,
            d=effective_d,
            s_conf=s_conf,
            s_mid=s_mid,
            ox=ox,
        )
    else:
        stirrup_positions = compute_symmetric_stirrup_positions(
            span_mm=span_mm,
            support_width_mm=support_width_mm,
            stirrup_spacing=stirrup_spacing,
            ox=ox,
        )

    for sx in stirrup_positions:
        msp.add_line((sx, stirrup_bot_y), (sx, stirrup_top_y), dxfattribs={"layer": "STIRRUPS"})

    # 6. Dimensions
    if is_seismic and left_conf_end < right_conf_start:
        # 3-Zone Confinement Dimensions
        draw_dimension_horizontal(
            msp,
            ox + support_width_mm,
            left_conf_end,
            oy,
            f"2d = {int(round(2*effective_d))} mm (@{int(round(s_conf))})",
            offset=45.0,
            text_height=11.0,
        )
        draw_dimension_horizontal(
            msp,
            left_conf_end,
            right_conf_start,
            oy,
            f"Midspan (@{int(round(s_mid))})",
            offset=45.0,
            text_height=11.0,
        )
        draw_dimension_horizontal(
            msp,
            right_conf_start,
            rx,
            oy,
            f"2d = {int(round(2*effective_d))} mm (@{int(round(s_conf))})",
            offset=45.0,
            text_height=11.0,
        )
        dim_clear_span_offset = 85.0
        dim_total_len_offset = 130.0
        # Callout at top
        z_name = seismic_zone or "IV"
        msp.add_text(
            f"IS 13920:2016 SEISMIC DUCTILE DETAILING (Zone {z_name})",
            dxfattribs={"layer": "ANNOTATIONS", "height": 13.0},
        ).set_placement((ox + support_width_mm, oy + D + 40.0), align=ezdxf.enums.TextEntityAlignment.BOTTOM_LEFT)
    else:
        dim_clear_span_offset = 60.0
        dim_total_len_offset = 120.0

    # Clear Span
    draw_dimension_horizontal(
        msp,
        ox + support_width_mm,
        ox + support_width_mm + span_mm,
        oy,
        f"Clear Span L = {int(round(span_mm))} mm",
        offset=dim_clear_span_offset,
    )
    # Total Beam Length
    draw_dimension_horizontal(
        msp,
        ox,
        ox + total_length,
        oy,
        f"Total Length = {int(round(total_length))} mm",
        offset=dim_total_len_offset,
    )
    # Support Widths
    draw_dimension_horizontal(
        msp,
        ox,
        ox + support_width_mm,
        oy,
        f"{int(round(support_width_mm))}",
        offset=30.0,
        text_height=11.0,
    )

    # 7. Section Cut Indicators (A-A at midspan)
    mid_span_x = ox + support_width_mm + (span_mm / 2.0)
    msp.add_line((mid_span_x, oy - 40.0), (mid_span_x, oy + D + 40.0), dxfattribs={"layer": "ANNOTATIONS"})
    txt_a1 = msp.add_text("A", dxfattribs={"layer": "ANNOTATIONS", "height": 20.0})
    txt_a1.set_placement((mid_span_x, oy + D + 45.0), align=ezdxf.enums.TextEntityAlignment.BOTTOM_CENTER)
    txt_a2 = msp.add_text("A", dxfattribs={"layer": "ANNOTATIONS", "height": 20.0})
    txt_a2.set_placement((mid_span_x, oy - 45.0), align=ezdxf.enums.TextEntityAlignment.TOP_CENTER)

    # Elevation Title
    el_title = msp.add_text("LONGITUDINAL ELEVATION", dxfattribs={"layer": "ANNOTATIONS", "height": 22.0})
    el_title.set_placement((ox + total_length / 2.0, oy - (dim_total_len_offset + 50.0)), align=ezdxf.enums.TextEntityAlignment.TOP_CENTER)


def draw_notes_and_compliance_table(
    msp: Modelspace,
    origin: Tuple[float, float],
    design: Dict[str, Any],
    box_width: float = 1400.0,
) -> float:
    """Renders the IS 456:2000 Structural Notes and Compliance Citations box with word-wrapped text."""
    ox, oy = origin
    line_height = 20.0

    b = design.get("b", 300)
    D = design.get("D", 500)
    fck = design.get("fck", 25)
    fy = design.get("fy", 500)
    exposure = design.get("exposure", "Moderate")
    cover_mm = design.get("cover_mm", 30)
    main_dia = design.get("main_bar_dia_mm", 16)
    main_cnt = design.get("main_bar_count", 3)
    comp_dia = design.get("compression_bar_dia_mm", 10)
    comp_cnt = design.get("compression_bar_count", 2)
    stirrup_dia = design.get("stirrup_dia_mm", 8)
    stirrup_spacing = design.get("stirrup_spacing_mm", 150)
    shear_status = design.get("shear_status", "minimum_shear_steel_ok")
    tau_v = design.get("tau_v")
    tau_c = design.get("tau_c")
    vus = design.get("vus")

    tau_v_str = f"{float(tau_v):.3f}" if tau_v is not None else "N/A"
    tau_c_str = f"{float(tau_c):.3f}" if tau_c is not None else "N/A"
    if vus is not None and float(vus) > 0:
        vus_str = f"{float(vus)/1000.0:.2f} kN ({float(vus):.1f} N)"
    elif vus is not None:
        vus_str = "0.00 kN (tau_v <= tau_c)"
    else:
        vus_str = "0.00 kN"

    if shear_status == "needs_shear_design":
        stirrup_note = (
            f"5. Shear Reinforcement: 2-legged closed stirrups T{int(round(float(stirrup_dia)))} @ "
            f"{int(round(float(stirrup_spacing)))} mm c/c (IS 456:2000 Cl. 40.4, 26.5.1.5, 26.5.1.6). "
            f"tau_v = {tau_v_str} N/mm2, tau_c = {tau_c_str} N/mm2, Vus = {vus_str}, Spacing = {int(round(float(stirrup_spacing)))} mm. "
            f"Stirrup spacing NOT designed for shear."
        )
    else:
        stirrup_note = (
            f"5. Shear Reinforcement: 2-legged closed stirrups T{int(round(float(stirrup_dia)))} @ "
            f"{int(round(float(stirrup_spacing)))} mm c/c (IS 456:2000 Cl. 40.4, 26.5.1.5, 26.5.1.6). "
            f"tau_v = {tau_v_str} N/mm2, tau_c = {tau_c_str} N/mm2, Vus = {vus_str}, Spacing = {int(round(float(stirrup_spacing)))} mm."
        )

    raw_notes = [
        f"1. Materials: Concrete Grade M{int(round(float(fck)))}, Reinforcing Steel Fe {int(round(float(fy)))} TMT bars.",
        f"2. Environmental Exposure: {exposure}. Nominal concrete cover provided = {int(round(float(cover_mm)))} mm (IS 456:2000 Table 16).",
        f"3. Tension Steel: {main_cnt}-T{int(round(float(main_dia)))} mm bars complying with minimum (Cl. 26.5.1.1(a)) and maximum (Cl. 26.5.1.1(b)) limits.",
        f"4. Compression / Hanger Bars: {comp_cnt}-T{int(round(float(comp_dia)))} mm bars provided for stirrup anchorage.",
        stirrup_note,
        f"6. Shear Stress: Maximum shear stress tau_c_max verified per IS 456:2000 Table 20.",
        f"7. Flexural Resistance: Calculated deterministically per IS 456:2000 Annex G-1.1 & Cl. 38.1.",
        "8. Development and lap lengths: as per IS 456:2000 Cl. 26.2, to be specified by the structural engineer (not computed by this tool).",
        "9. Shear Design Basis: Table 19 row rule (row at or below pt) is an assumption, not from IS 456 standard; Vu is taken at support face without Cl. 40.5.3 reduction; ast_provided is full tension steel (Table 19 note also depends on anchorage not implemented).",
        "10. Construction to be executed strictly in accordance with approved structural engineering drawings.",
    ]

    is_seismic = bool(
        design.get("is_seismic", False)
        or design.get("is_ductile", False)
        or str(design.get("seismic_zone", "")).upper() in ["III", "IV", "V"]
    )
    if is_seismic:
        raw_notes.append("11. Seismic Ductile Detailing: Complies with IS 13920:2016 Cl. 6.3.3. Support confinement spacing <= 100 mm over 2d.")
        raw_notes.append("12. Seismic Hooks: 135° closed stirrups with extension length >= 10*db (min 65 mm) per IS 13920:2016 Cl. 5.2.")

    # Wrap notes to max 140 chars so every line stays strictly inside the 1400mm box border
    wrapped_lines: List[Tuple[str, bool]] = [
        ("IS 456:2000 STRUCTURAL COMPLIANCE & EXECUTION NOTES", True)
    ]
    for note in raw_notes:
        chunks = textwrap.wrap(note, width=140)
        for idx, chunk in enumerate(chunks):
            indent_prefix = "" if idx == 0 else "   "
            wrapped_lines.append((indent_prefix + chunk, False))

    box_height = len(wrapped_lines) * line_height + 35.0

    # Draw notes box border
    msp.add_lwpolyline(
        [(ox, oy), (ox + box_width, oy), (ox + box_width, oy - box_height), (ox, oy - box_height), (ox, oy)],
        close=True,
        dxfattribs={"layer": "TITLE_BLOCK"},
    )

    # Add notes text
    for i, (line_text, is_heading) in enumerate(wrapped_lines):
        ty = oy - 22.0 - (i * line_height)
        h = 13.0 if is_heading else 9.5
        color_layer = "TITLE_BLOCK" if is_heading else "ANNOTATIONS"
        msp.add_text(
            line_text,
            dxfattribs={"layer": color_layer, "height": h},
        ).set_placement((ox + 20.0, ty), align=ezdxf.enums.TextEntityAlignment.MIDDLE_LEFT)

    return box_height


def draw_title_block(
    msp: Modelspace,
    origin: Tuple[float, float],
    design: Dict[str, Any],
) -> None:
    """Draws a professional CAD title block with project metadata."""
    ox, oy = origin
    tb_width = 1100.0
    tb_height = 140.0

    msp.add_lwpolyline(
        [(ox, oy), (ox + tb_width, oy), (ox + tb_width, oy - tb_height), (ox, oy - tb_height), (ox, oy)],
        close=True,
        dxfattribs={"layer": "TITLE_BLOCK"},
    )

    # Dividing lines
    msp.add_line((ox, oy - 45.0), (ox + tb_width, oy - 45.0), dxfattribs={"layer": "TITLE_BLOCK"})
    msp.add_line((ox, oy - 90.0), (ox + tb_width, oy - 90.0), dxfattribs={"layer": "TITLE_BLOCK"})
    msp.add_line((ox + 550.0, oy - 45.0), (ox + 550.0, oy - 90.0), dxfattribs={"layer": "TITLE_BLOCK"})

    # Title & Project Details
    t1 = msp.add_text("IS 456:2000 STRUCTURAL RC BEAM DESIGN", dxfattribs={"layer": "TITLE_BLOCK", "height": 18.0})
    t1.set_placement((ox + tb_width / 2.0, oy - 25.0), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)

    t2 = msp.add_text("DRAWING: BEAM REINFORCEMENT & SECTION DETAILS", dxfattribs={"layer": "TITLE_BLOCK", "height": 12.0})
    t2.set_placement((ox + 20.0, oy - 68.0), align=ezdxf.enums.TextEntityAlignment.MIDDLE_LEFT)

    t3 = msp.add_text("CODE: IS 456:2000 | SCALE: NTS (ALL DIMS IN MM)", dxfattribs={"layer": "TITLE_BLOCK", "height": 11.0})
    t3.set_placement((ox + 570.0, oy - 68.0), align=ezdxf.enums.TextEntityAlignment.MIDDLE_LEFT)

    reviewer_name = design.get("reviewer_name")
    reviewer_role = design.get("reviewer_role")
    review_date = design.get("review_date")
    outcome = design.get("outcome") or design.get("review_outcome")

    if reviewer_name and reviewer_role and review_date:
        outcome_str = outcome or "Reviewed"
        status_text = f"Reviewed by {reviewer_name}, {review_date}: {outcome_str}"
    else:
        status_text = "STATUS: DRAFT - NOT FOR CONSTRUCTION. Not engineer-reviewed."

    t4 = msp.add_text(status_text, dxfattribs={"layer": "TITLE_BLOCK", "height": 9.5})
    t4.set_placement((ox + 20.0, oy - 115.0), align=ezdxf.enums.TextEntityAlignment.MIDDLE_LEFT)


def generate_beam_dxf(
    design: Dict[str, Any],
    output_path: Optional[str] = None,
) -> Drawing:
    """
    Generates a 2D DXF drawing of an RC beam from design parameters.

    Args:
        design: Dictionary containing b, D, d, fck, fy, exposure,
                main_bar_dia_mm, main_bar_count,
                compression_bar_dia_mm, compression_bar_count,
                stirrup_dia_mm, stirrup_spacing_mm,
                and optional span_m / cover_mm.
        output_path: Optional file path string to save the generated .dxf file.

    Returns:
        ezdxf.document.Drawing instance.
    """
    # 1. Initialize DXF Document (AutoCAD R2010 DXF standard)
    # Use standard AutoCAD linetypes without injecting unused external TTF styles
    # that trigger Autodesk Viewer cloud font substitution warnings
    doc = ezdxf.new("R2010", setup=["linetypes"])
    doc.units = 4  # Millimetres
    doc.header["$INSUNITS"] = 4
    setup_layers(doc)
    msp = doc.modelspace()

    # 2. Extract & Validate Parameters
    b = float(design.get("b", 300.0))
    D = float(design.get("D", 500.0))
    d = float(design.get("d", D - 50.0))
    exposure = str(design.get("exposure", "Moderate"))

    # Cover from Table 16 if not directly passed
    if "cover_mm" in design and design["cover_mm"]:
        cover_mm = float(design["cover_mm"])
    else:
        cover_mm = float(nominal_cover(exposure)["required"])
    design["cover_mm"] = cover_mm

    main_bar_dia = float(design.get("main_bar_dia_mm", 16.0))
    main_bar_count = int(design.get("main_bar_count", 3))
    comp_bar_dia = float(design.get("compression_bar_dia_mm", 10.0))
    comp_bar_count = int(design.get("compression_bar_count", 2))
    stirrup_dia = float(design.get("stirrup_dia_mm", 8.0))
    stirrup_spacing = float(design.get("stirrup_spacing_mm", 150.0))
    span_m = float(design.get("span_m", 4.5))
    span_mm = span_m * 1000.0

    is_seismic = bool(
        design.get("is_seismic", False)
        or design.get("is_ductile", False)
        or str(design.get("seismic_zone", "")).upper() in ["III", "IV", "V"]
    )
    seismic_zone = str(design.get("seismic_zone", "IV")) if is_seismic else None

    # 3. Layout Positioning
    support_width_mm = 300.0
    total_length = span_mm + 2.0 * support_width_mm

    # Cross-section at origin (0, 0)
    draw_cross_section(
        msp=msp,
        origin=(0.0, 0.0),
        b=b,
        D=D,
        d=d,
        cover_mm=cover_mm,
        main_bar_dia=main_bar_dia,
        main_bar_count=main_bar_count,
        comp_bar_dia=comp_bar_dia,
        comp_bar_count=comp_bar_count,
        stirrup_dia=stirrup_dia,
        stirrup_spacing=stirrup_spacing,
        is_seismic=is_seismic,
    )

    # Longitudinal Elevation to the right
    elevation_x = b + 500.0
    draw_longitudinal_elevation(
        msp=msp,
        origin=(elevation_x, 0.0),
        span_mm=span_mm,
        b=b,
        D=D,
        cover_mm=cover_mm,
        main_bar_dia=main_bar_dia,
        main_bar_count=main_bar_count,
        comp_bar_dia=comp_bar_dia,
        comp_bar_count=comp_bar_count,
        stirrup_dia=stirrup_dia,
        stirrup_spacing=stirrup_spacing,
        support_width_mm=support_width_mm,
        d=d,
        is_seismic=is_seismic,
        seismic_zone=seismic_zone,
    )

    # Notes Box at bottom-left below Cross-Section
    notes_y = -350.0
    notes_box_width = 1400.0
    draw_notes_and_compliance_table(
        msp=msp,
        origin=(0.0, notes_y),
        design=design,
        box_width=notes_box_width,
    )

    # Title Block at bottom-right aligned with beam end (safe clearance from notes box)
    title_block_x = max(notes_box_width + 100.0, elevation_x + total_length - 1100.0)
    draw_title_block(
        msp=msp,
        origin=(title_block_x, notes_y),
        design=design,
    )

    # 4. Save to Disk if Output Path Given
    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        doc.saveas(str(out_p))

    return doc


def export_dxf_from_design(
    design: Dict[str, Any],
    output_path: Optional[str] = None,
    output_filename: Optional[str] = None,
    validate_first: bool = True,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Validates design against deterministic IS 456 checks and exports a 2D DXF drawing.
    Supports either output_path or output_filename keyword arguments.

    Returns:
        Dict with "status", "dxf_path", "validation", and "is456_citations".
    """
    dest_path = output_path or output_filename or kwargs.get("filepath") or "beam_design.dxf"
    validation_res = None
    if validate_first:
        validation_res = validate_design(design)
        if validation_res["status"] != "passed":
            return {
                "status": "failed_validation",
                "dxf_path": None,
                "validation": validation_res,
                "notes": "Design did not pass deterministic IS 456 checks. DXF export halted for safety.",
            }

    doc = generate_beam_dxf(design, output_path=dest_path)

    return {
        "status": "success",
        "dxf_path": str(Path(dest_path).resolve()),
        "validation": validation_res,
        "is456_citations": [
            "IS 456:2000 Cl. 26.5.1.1",
            "IS 456:2000 Cl. 26.5.1.5",
            "IS 456:2000 Cl. 26.5.1.6",
            "IS 456:2000 Cl. 40.4",
            "IS 456:2000 Table 16",
            "IS 456:2000 Table 19",
            "IS 456:2000 Table 20",
        ],
    }


def export_dxf_from_loads(
    span_m: float,
    dead_load_kN_per_m: float,
    live_load_kN_per_m: float,
    fck: float = 25.0,
    fy: float = 500.0,
    exposure: str = "Moderate",
    output_path: str = "data/processed/cad/beam_design.dxf",
) -> Dict[str, Any]:
    """
    End-to-End Workflow:
    Takes Span and Loads -> Sizes Beam -> Verifies IS 456 Checks -> Generates 2D CAD DXF Drawing.
    """
    from src.generation.beam_sizing import size_beam_from_loads

    sizing_res = size_beam_from_loads(
        span_m=span_m,
        dead_load_kN_per_m=dead_load_kN_per_m,
        live_load_kN_per_m=live_load_kN_per_m,
        fck=fck,
        fy=fy,
        exposure=exposure,
    )

    if sizing_res.get("status") == "needs_review":
        return {
            "status": "needs_review",
            "reason": sizing_res.get("reason"),
            "dxf_path": None,
            "sizing": sizing_res,
            "validation": None,
            "shear_status": sizing_res.get("shear_status", "needs_review"),
        }

    design_dict = sizing_res["design_dict"]
    design_dict["span_m"] = span_m

    dxf_result = export_dxf_from_design(
        design=design_dict,
        output_path=output_path,
        validate_first=True,
    )

    return {
        "status": dxf_result["status"],
        "dxf_path": dxf_result.get("dxf_path"),
        "sizing": sizing_res,
        "validation": dxf_result.get("validation"),
        "shear_status": sizing_res.get("shear_status"),
        "is456_citations": dxf_result.get("is456_citations"),
    }
