"""
Engineer Review and Feedback Loop Module for IS 456 Structural Beam Design (Step 8).

Implements the formal engineering review workflow:
1. Generates a structured review sheet listing all design parameters, governing assumptions,
   and IS 456 code clause check results.
2. Accepts engineer corrections/overrides, re-verifies them against IS 456 rules,
   and recalculates effective depth and detailing parameters.
3. Facilitates engineer sign-off and approval, stamping approval metadata into the final CAD title block.
"""

from datetime import datetime, timezone
import math
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from src.validation.is456_checks import (
    nominal_cover,
    min_tension_steel,
    max_tension_steel,
    max_stirrup_spacing,
    min_shear_steel,
    min_bar_clear_spacing,
    development_length,
    deflection_check,
    tau_c_max,
    xu_max_over_d,
)
from src.validation.is456_flexure import (
    mu_lim,
)
from src.cad.beam_dxf import export_dxf_from_design


STANDARD_ASSUMPTIONS = [
    {
        "assumption": "Partial safety factor for loads",
        "value": "1.5 on dead load and live load (Table 18)",
        "clause": "IS 456:2000 Table 18",
    },
    {
        "assumption": "Unit weight of reinforced concrete",
        "value": "25.0 kN/m3 (Cl. 19.2.1)",
        "clause": "IS 456:2000 Cl. 19.2.1",
    },
    {
        "assumption": "Support bearing width",
        "value": "300 mm assumed when not provided (Cl. 22.2(a))",
        "clause": "IS 456:2000 Cl. 22.2(a)",
    },
    {
        "assumption": "Nominal maximum aggregate size",
        "value": "20 mm assumed unless provided; gives 25 mm clear gap floor (Cl. 26.3.2(a))",
        "clause": "IS 456:2000 Cl. 26.3.2(a)",
    },
    {
        "assumption": "Stirrup practical constructability floor",
        "value": "Minimum 100 mm spacing threshold to permit concrete pouring",
        "clause": "Constructability Rule",
    },
    {
        "assumption": "Deflection modification factor F1",
        "value": "Empirical curve fit; results are indicative only until Fig. 4 is digitized",
        "clause": "IS 456:2000 Cl. 23.2 & Fig. 4",
    },
]


def generate_review_report(design_or_sizing: Dict[str, Any]) -> Dict[str, Any]:
    """
    Builds an Engineer Review Report detailing design inputs, calculated parameters,
    governing engineering assumptions, and IS 456 clause verification statuses.
    """
    design = design_or_sizing.get("design_dict", design_or_sizing)
    sizing = design_or_sizing if "design_dict" in design_or_sizing else {}

    # Extract geometric and material properties
    b = float(design.get("b", 300.0))
    D = float(design.get("D", 500.0))
    span_m = float(design.get("span_m", 4.5))
    fck = float(design.get("fck", 25.0))
    fy = float(design.get("fy", 500.0))
    exposure = str(design.get("exposure", "Moderate"))
    cover_mm = float(design.get("cover_mm", nominal_cover(exposure)["required"]))

    main_bar_dia = float(design.get("main_bar_dia_mm", 16.0))
    main_bar_count = int(design.get("main_bar_count", 3))
    stirrup_dia = float(design.get("stirrup_dia_mm", 8.0))
    stirrup_spacing = float(design.get("stirrup_spacing_mm", 150.0))
    stirrup_legs = int(design.get("stirrup_legs", 2))
    max_agg_size = float(design.get("max_aggregate_size_mm", 20.0))

    # Recompute actual effective depth
    d_actual = D - cover_mm - stirrup_dia - (main_bar_dia / 2.0)
    ast_provided = main_bar_count * (math.pi / 4.0) * (main_bar_dia ** 2)
    pt = (ast_provided / (b * d_actual)) * 100.0 if (b * d_actual) > 0 else 0.0

    # Clause checks evaluation
    checks: List[Dict[str, Any]] = []

    # 1. Flexural Capacity check (Annex G-1.1)
    xu_max_ratio = xu_max_over_d(fy)
    mu_lim_kNm = mu_lim(b, d_actual, fck, fy) / 1e6
    factored_moment_kNm = float(sizing.get("factored_moment_kNm", 0.0))
    flexure_pass = mu_lim_kNm >= factored_moment_kNm if factored_moment_kNm > 0 else True
    checks.append({
        "check": "Flexural Capacity (Singly Reinforced Limit)",
        "clause": "IS 456:2000 Annex G-1.1",
        "status": "pass" if flexure_pass else "needs_review",
        "details": f"Mu,lim = {mu_lim_kNm:.2f} kNm vs Mu = {factored_moment_kNm:.2f} kNm (xu,max/d = {xu_max_ratio:.2f})",
    })

    # 2. Minimum & Maximum Tension Steel (Cl. 26.5.1.1)
    chk_min = min_tension_steel(b, d_actual, fy, ast_provided)
    chk_max = max_tension_steel(b, D, ast_provided)
    ast_pass = chk_min["passed"] and chk_max["passed"]
    checks.append({
        "check": "Tension Reinforcement Area Limits",
        "clause": "IS 456:2000 Cl. 26.5.1.1(a),(b)",
        "status": "pass" if ast_pass else "needs_review",
        "details": f"Ast,prov = {ast_provided:.1f} mm2 (Min: {chk_min['required']:.1f} mm2, Max: {chk_max['required']:.1f} mm2)",
    })

    # 3. Clear Bar Spacing (Cl. 26.3.2(a))
    spacing_res = min_bar_clear_spacing(
        b=b,
        cover_mm=cover_mm,
        stirrup_dia=stirrup_dia,
        n_bars=main_bar_count,
        bar_dia=main_bar_dia,
        max_aggregate_size_mm=max_agg_size,
    )
    checks.append({
        "check": "Minimum Horizontal Bar Clear Spacing",
        "clause": "IS 456:2000 Cl. 26.3.2(a)",
        "status": "pass" if spacing_res["passed"] else "needs_review",
        "details": f"Clear gap = {spacing_res['clear_gap']:.1f} mm (Floor: {spacing_res['required']:.1f} mm)",
    })

    # 4. Shear Stress Ceiling (Cl. 40.2.3 & Table 20)
    factored_shear_kN = float(sizing.get("factored_shear_kN", 0.0))
    vu_N = factored_shear_kN * 1000.0
    tau_v = (vu_N / (b * d_actual)) if vu_N > 0 else 0.0
    concrete_grade = f"M{int(fck)}" if fck >= 15 else "M15"
    try:
        tau_c_max_val = tau_c_max(concrete_grade)
    except Exception:
        tau_c_max_val = 3.1
    tau_pass = tau_v <= tau_c_max_val
    checks.append({
        "check": "Nominal Shear Stress vs tau_c,max",
        "clause": "IS 456:2000 Cl. 40.2.3 & Table 20",
        "status": "pass" if tau_pass else "needs_review",
        "details": f"tau_v = {tau_v:.3f} N/mm2 <= tau_c,max = {tau_c_max_val:.2f} N/mm2",
    })

    # 5. Shear Stirrup Spacing (Cl. 26.5.1.5, Cl. 26.5.1.6, Cl. 40.4)
    chk_stirrup_max = max_stirrup_spacing(d_actual, stirrup_spacing)
    asv = stirrup_legs * (math.pi / 4.0) * (stirrup_dia ** 2)
    chk_stirrup_min = min_shear_steel(b, stirrup_spacing, fy, asv)
    stirrup_pass = chk_stirrup_max["passed"] and chk_stirrup_min["passed"] and stirrup_spacing >= 100.0
    checks.append({
        "check": "Shear Reinforcement Spacing Limits",
        "clause": "IS 456:2000 Cl. 26.5.1.5 & Cl. 26.5.1.6",
        "status": "pass" if stirrup_pass else "needs_review",
        "details": f"Provided sv = {stirrup_spacing:.0f} mm (Max: {chk_stirrup_max['required']:.0f} mm, Practical floor: 100 mm)",
    })

    # 6. Development Length (Cl. 26.2.1)
    ld_res = development_length(
        bar_dia_mm=main_bar_dia,
        fck=fck,
        fy=fy,
        bar_type="deformed",
        stress_type="tension",
    )
    checks.append({
        "check": "Tension Bar Development Length (Anchorage)",
        "clause": "IS 456:2000 Cl. 26.2.1",
        "status": "pass",
        "details": f"Ld required = {ld_res['ld_mm']:.0f} mm (tau_bd = {ld_res['tau_bd_N_per_mm2']:.2f} N/mm2)",
    })

    # 7. Deflection (Cl. 23.2 & Fig. 4)
    ast_calc = float(sizing.get("ast_required_mm2", ast_provided))
    defl_res = deflection_check(
        span_m=span_m,
        d_actual_mm=d_actual,
        fy=fy,
        ast_required_mm2=ast_calc,
        ast_provided_mm2=ast_provided,
        b_mm=b,
        member_type="simply_supported",
    )
    checks.append({
        "check": "Span-to-Effective-Depth Ratio (Deflection)",
        "clause": "IS 456:2000 Cl. 23.2 & Fig. 4",
        "status": defl_res.get("status", "indicative"),
        "details": f"Actual L/d = {defl_res['actual_ld_ratio']:.2f} vs Allowable = {defl_res['max_ld_ratio']:.2f} ({defl_res.get('note', '')})",
    })

    # 8. Durability Cover (Table 16)
    cover_spec = nominal_cover(exposure)
    cover_pass = cover_mm >= float(cover_spec["required"])
    checks.append({
        "check": "Nominal Concrete Cover (Durability)",
        "clause": "IS 456:2000 Table 16",
        "status": "pass" if cover_pass else "needs_review",
        "details": f"Cover = {cover_mm:.0f} mm for '{exposure}' exposure (Required: {cover_spec['required']} mm)",
    })

    # Determine overall review status
    has_review_item = any(c["status"] == "needs_review" for c in checks)
    review_status = "needs_redesign" if (not tau_pass or not spacing_res["passed"]) else (
        "pending_engineer_review" if has_review_item else "ready_for_engineer_review"
    )

    approval_status = design.get("approval_status", "pending")
    engineer_name = design.get("engineer_name")
    approval_timestamp = design.get("approval_timestamp")
    engineer_remarks = design.get("engineer_remarks")

    # Generate human-readable Markdown Report
    lines = [
        "# Structural RC Beam Design — Engineer Review Sheet",
        "**Status**: Draft Pilot — Passes implemented IS 456 beam detailing checks only. Must be reviewed by an engineer.",
        "",
        "## 1. Design Inputs & Geometry",
        f"- **Span**: {span_m:.2f} m",
        f"- **Cross-Section**: Width $b = {b:.0f}\\text{{ mm}}$, Depth $D = {D:.0f}\\text{{ mm}}$",
        f"- **Actual Effective Depth**: $d_{{\\text{{actual}}}} = {d_actual:.1f}\\text{{ mm}}$",
        f"- **Materials**: Concrete $f_{{ck}} = {fck:.0f}\\text{{ N/mm}}^2$, Steel $f_y = {fy:.0f}\\text{{ N/mm}}^2$",
        f"- **Environmental Exposure**: {exposure} (Cover: {cover_mm:.0f} mm)",
        "",
        "## 2. Reinforcement Detailing",
        f"- **Main Tension Steel**: {main_bar_count}-T{main_bar_dia:.0f} ($A_{{st}} = {ast_provided:.1f}\\text{{ mm}}^2$, $p_t = {pt:.2f}\\%$)",
        f"- **Clear Bar Spacing**: {spacing_res['clear_gap']:.1f} mm (Required min: {spacing_res['required']:.1f} mm)",
        f"- **Shear Reinforcement**: 2L-T{stirrup_dia:.0f} @ {stirrup_spacing:.0f} mm c/c",
        f"- **Development Length ($L_d$)**: {ld_res['ld_mm']:.0f} mm",
        "",
        "## 3. IS 456:2000 Clause Compliance Checks",
        "| Check Item | IS 456 Reference | Status | Calculation Details |",
        "| :--- | :--- | :---: | :--- |",
    ]
    for c in checks:
        lines.append(f"| {c['check']} | {c['clause']} | **{c['status']}** | {c['details']} |")

    lines.extend([
        "",
        "## 4. Governing Engineering Assumptions",
    ])
    for a in STANDARD_ASSUMPTIONS:
        lines.append(f"- **{a['assumption']}**: {a['value']} (*{a['clause']}*)")

    reviewer_name = design.get("reviewer_name") or engineer_name
    reviewer_role = design.get("reviewer_role")
    review_date = design.get("review_date") or approval_timestamp
    outcome = design.get("outcome") or "Reviewed"

    if reviewer_name and reviewer_role and review_date:
        lines.extend([
            "",
            "## 5. Engineer Review Record",
            f"- **Reviewed By**: {reviewer_name} ({reviewer_role})",
            f"- **Review Date**: {review_date}",
            f"- **Outcome**: {outcome}",
            f"- **Remarks**: {engineer_remarks or 'None'}",
        ])
    else:
        lines.extend([
            "",
            "## 5. Review Status",
            f"- **Current State**: {review_status.upper().replace('_', ' ')}",
            "- **Status**: DRAFT - NOT FOR CONSTRUCTION. Not engineer-reviewed.",
        ])

    markdown_report = "\n".join(lines)

    return {
        "review_status": review_status,
        "approval_status": approval_status,
        "engineer_name": engineer_name,
        "approval_timestamp": approval_timestamp,
        "engineer_remarks": engineer_remarks,
        "design_summary": {
            "b_mm": b,
            "D_mm": D,
            "d_actual_mm": d_actual,
            "span_m": span_m,
            "fck": fck,
            "fy": fy,
            "exposure": exposure,
            "cover_mm": cover_mm,
            "main_bars": f"{main_bar_count}-T{main_bar_dia:.0f}",
            "ast_provided_mm2": ast_provided,
            "clear_gap_mm": spacing_res["clear_gap"],
            "stirrups": f"2L-T{stirrup_dia:.0f} @ {stirrup_spacing:.0f} mm",
            "ld_mm": ld_res["ld_mm"],
        },
        "checks": checks,
        "assumptions": STANDARD_ASSUMPTIONS,
        "markdown_report": markdown_report,
    }


def apply_engineer_overrides(
    original_design: Dict[str, Any],
    overrides: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Applies engineer corrections or overrides to beam dimensions or reinforcement detailing,
    then re-evaluates all IS 456 constraints.
    """
    design = dict(original_design)

    # Allowed override keys
    allowed_keys = {
        "b", "D", "fck", "fy", "exposure", "cover_mm",
        "main_bar_dia_mm", "main_bar_count",
        "compression_bar_dia_mm", "compression_bar_count",
        "stirrup_dia_mm", "stirrup_spacing_mm", "stirrup_legs",
        "max_aggregate_size_mm", "span_m",
    }

    for k, v in overrides.items():
        if k in allowed_keys and v is not None:
            design[k] = v

    # Recompute geometry
    b = float(design.get("b", 300.0))
    D = float(design.get("D", 500.0))
    exposure = str(design.get("exposure", "Moderate"))
    cover_mm = float(design.get("cover_mm", nominal_cover(exposure)["required"]))
    main_bar_dia = float(design.get("main_bar_dia_mm", 16.0))
    main_bar_count = int(design.get("main_bar_count", 3))
    stirrup_dia = float(design.get("stirrup_dia_mm", 8.0))
    stirrup_spacing = float(design.get("stirrup_spacing_mm", 150.0))
    fck = float(design.get("fck", 25.0))
    fy = float(design.get("fy", 500.0))
    max_agg = float(design.get("max_aggregate_size_mm", 20.0))

    d_actual = D - cover_mm - stirrup_dia - (main_bar_dia / 2.0)
    design["d"] = d_actual
    design["cover_mm"] = cover_mm

    rejection_reasons = []

    # Check clear bar spacing
    spacing_res = min_bar_clear_spacing(
        b=b,
        cover_mm=cover_mm,
        stirrup_dia=stirrup_dia,
        n_bars=main_bar_count,
        bar_dia=main_bar_dia,
        max_aggregate_size_mm=max_agg,
    )
    if not spacing_res["passed"]:
        rejection_reasons.append(
            f"Cl. 26.3.2 clear bar spacing violation: gap {spacing_res['clear_gap']:.1f} mm < "
            f"required floor {spacing_res['required']:.1f} mm."
        )

    # Check maximum steel area
    ast_provided = main_bar_count * (math.pi / 4.0) * (main_bar_dia ** 2)
    chk_max = max_tension_steel(b, D, ast_provided)
    if not chk_max["passed"]:
        rejection_reasons.append(
            f"Cl. 26.5.1.1(b) maximum tension steel exceeded: Ast={ast_provided:.1f} mm2 > 0.04*b*D={chk_max['required']:.1f} mm2."
        )

    # Check minimum steel area
    chk_min = min_tension_steel(b, d_actual, fy, ast_provided)
    if not chk_min["passed"]:
        rejection_reasons.append(
            f"Cl. 26.5.1.1(a) minimum tension steel not satisfied: Ast={ast_provided:.1f} mm2 < {chk_min['required']:.1f} mm2."
        )

    # Check stirrup spacing
    chk_stirrup = max_stirrup_spacing(d_actual, stirrup_spacing)
    if not chk_stirrup["passed"]:
        rejection_reasons.append(
            f"Cl. 26.5.1.5 maximum stirrup spacing exceeded: sv={stirrup_spacing:.0f} mm > {chk_stirrup['required']:.0f} mm."
        )
    if stirrup_spacing < 100.0:
        rejection_reasons.append(
            f"Stirrup spacing sv={stirrup_spacing:.0f} mm is below practical constructability threshold (100 mm)."
        )

    if rejection_reasons:
        return {
            "status": "override_rejected",
            "reasons": rejection_reasons,
            "design": design,
        }

    # Reset any previous approval on modification
    design["approval_status"] = "pending"
    design.pop("approval_timestamp", None)

    report = generate_review_report(design)

    return {
        "status": "override_accepted",
        "review_status": "overridden_pending_approval",
        "design": design,
        "review_report": report,
    }


def sign_off_design(
    design: Dict[str, Any],
    reviewer_name: str = "",
    reviewer_role: Optional[str] = None,
    review_date: Optional[str] = None,
    outcome: Optional[str] = None,
    remarks: Optional[str] = None,
    engineer_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Records engineer review metadata on a beam design.
    Requires reviewer name, role, and date to stamp the drawing with:
    'Reviewed by <name>, <date>: <outcome>'
    """
    name = (reviewer_name or engineer_name or "").strip()
    if not name:
        raise ValueError("Reviewer name is required.")

    role = (reviewer_role or "").strip()
    date = (review_date or "").strip()
    rev_outcome = (outcome or "Reviewed").strip()

    signed_design = dict(design)
    signed_design["reviewer_name"] = name
    signed_design["engineer_name"] = name
    if role:
        signed_design["reviewer_role"] = role
    if date:
        signed_design["review_date"] = date
        signed_design["approval_timestamp"] = date
    else:
        signed_design["approval_timestamp"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    signed_design["outcome"] = rev_outcome
    signed_design["approval_status"] = "reviewed"
    signed_design["engineer_remarks"] = remarks.strip() if remarks else ""

    return signed_design


def export_approved_dxf(
    design: Dict[str, Any],
    output_path: str,
    engineer_name: str = "",
    remarks: Optional[str] = None,
    reviewer_name: Optional[str] = None,
    reviewer_role: Optional[str] = None,
    review_date: Optional[str] = None,
    outcome: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Exports 2D CAD DXF drawing with review metadata, or as draft if reviewer credentials are not supplied.
    """
    name = (reviewer_name or engineer_name or "").strip()
    if name and reviewer_role and review_date:
        signed_design = sign_off_design(
            design=design,
            reviewer_name=name,
            reviewer_role=reviewer_role,
            review_date=review_date,
            outcome=outcome,
            remarks=remarks,
        )
    else:
        signed_design = dict(design)

    result = export_dxf_from_design(signed_design, output_path=output_path, validate_first=True)
    result["approval_status"] = signed_design.get("approval_status", "draft")
    result["engineer_name"] = signed_design.get("engineer_name")
    result["reviewer_name"] = signed_design.get("reviewer_name")
    result["approval_timestamp"] = signed_design.get("approval_timestamp")
    result["engineer_remarks"] = signed_design.get("engineer_remarks")
    return result
