"""
Seismic Compliance & Code Conflict Resolution Engine (IS 456:2000 vs IS 13920:2016).

Step 6: Compliance Reasoning Engine / Conflict Resolution
Rule: In Seismic Zones III, IV, and V, ductile provisions of IS 13920:2016 supersede
general non-ductile requirements of IS 456:2000 for all lateral-load-resisting elements.

Key Governing Precedence:
1. Beam Width & Aspect Ratio:
   - IS 456: No mandatory minimum width.
   - IS 13920 Cl. 6.1.1: b >= 200 mm; b/D >= 0.30. (Governs)
2. Maximum Tension Reinforcement:
   - IS 456 Cl. 26.5.1.1(b): pt <= 4.0%.
   - IS 13920 Cl. 6.2.2: pt <= 2.50%. (Governs)
3. Minimum Longitudinal Steel:
   - IS 456 Cl. 26.5.1.1(a): pt >= 0.85 / fy (~0.20% for Fe 415).
   - IS 13920 Cl. 6.2.1: pt >= 0.24 * sqrt(fck) / fy (~0.29% for M25/Fe 415). (Governs)
4. Support Moment Capacity & Reversal:
   - IS 456: Ast,bottom at simple support >= Ast / 3.
   - IS 13920 Cl. 6.2.3: Positive moment capacity at joint face >= 50% of negative moment capacity;
     and moment capacity at any section along member >= 25% of max negative capacity. (Governs)
5. Beam Stirrups & Plastic Hinge Confinement:
   - IS 456 Cl. 26.5.1.5: sv <= min(0.75*d, 300 mm).
   - IS 13920 Cl. 6.3.3: Over length 2d from joint face, sv <= min(d/4, 8*db_min, 100 mm). (Governs)
6. Column Confinement Zone & Tie Pitch:
   - IS 456 Cl. 26.5.3.2: sv <= min(b, 16*db_min, 300 mm).
   - IS 13920 Cl. 7.6.1: Over length lo = max(D, H/6, 450 mm), sv <= min(b/4, 6*db_min, 100 mm; sv >= 65 mm). (Governs)
7. Rebar Hooks & Ties:
   - IS 456: 90° hooks with 8*db extension acceptable for links.
   - IS 13920 Cl. 5.2 & 5.3: Mandatory 135° seismic hooks with >= 10*db extension (min 65 mm). (Governs)
"""

import math
from typing import Dict, Any, List, Optional


def resolve_beam_seismic_conflicts(
    b: float,
    D: float,
    d: float,
    fck: float,
    fy: float,
    ast_provided: float,
    stirrup_dia: float,
    stirrup_spacing_midspan: float,
    db_min: float,
    seismic_zone: str = "IV",
    is_ductile: bool = True,
) -> Dict[str, Any]:
    """
    Evaluates beam design against IS 456 and IS 13920, automatically resolving conflicts
    and flagging governing seismic rules.
    """
    seismic_active = is_ductile or seismic_zone.upper() in ["III", "IV", "V"]
    checks: List[Dict[str, Any]] = []
    conflicts_resolved: List[Dict[str, Any]] = []

    # 1. Beam Width & Aspect Ratio
    is456_min_width = 200.0  # Industry standard recommendation
    is13920_min_width = 200.0
    is13920_min_ratio = 0.30
    actual_ratio = round(b / D, 3)

    width_passed = b >= is13920_min_width if seismic_active else b >= 150.0
    ratio_passed = actual_ratio >= is13920_min_ratio if seismic_active else True

    checks.append({
        "check": "beam_width",
        "value": b,
        "required_min": is13920_min_width if seismic_active else 150.0,
        "passed": width_passed,
        "governing_standard": "IS 13920:2016 Cl. 6.1.1" if seismic_active else "IS 456:2000",
    })
    checks.append({
        "check": "beam_width_to_depth_ratio",
        "value": actual_ratio,
        "required_min": is13920_min_ratio if seismic_active else 0.0,
        "passed": ratio_passed,
        "governing_standard": "IS 13920:2016 Cl. 6.1.1" if seismic_active else "IS 456:2000",
    })

    # 2. Minimum Tension Steel
    pt_provided = round((ast_provided / (b * d)) * 100.0, 3)
    pt_min_is456 = round((0.85 / fy) * 100.0, 3)
    pt_min_is13920 = round((0.24 * math.sqrt(fck) / fy) * 100.0, 3)
    pt_min_governing = pt_min_is13920 if seismic_active else pt_min_is456

    if seismic_active and pt_min_is13920 > pt_min_is456:
        conflicts_resolved.append({
            "parameter": "minimum_tension_steel_pt",
            "is456_limit": f"{pt_min_is456}% (Cl. 26.5.1.1a)",
            "is13920_limit": f"{pt_min_is13920}% (Cl. 6.2.1)",
            "governing": f"IS 13920:2016 Cl. 6.2.1 ({pt_min_is13920}%)",
            "reason": "Seismic cyclic reversals require higher ductile crack distribution steel.",
        })

    checks.append({
        "check": "min_tension_steel_pt",
        "value": pt_provided,
        "required_min": pt_min_governing,
        "passed": pt_provided >= pt_min_governing,
        "governing_standard": "IS 13920:2016 Cl. 6.2.1" if seismic_active else "IS 456:2000 Cl. 26.5.1.1(a)",
    })

    # 3. Maximum Tension Steel
    pt_max_is456 = 4.0
    pt_max_is13920 = 2.50
    pt_max_governing = pt_max_is13920 if seismic_active else pt_max_is456

    if seismic_active:
        conflicts_resolved.append({
            "parameter": "maximum_tension_steel_pt",
            "is456_limit": "4.00% (Cl. 26.5.1.1b)",
            "is13920_limit": "2.50% (Cl. 6.2.2)",
            "governing": "IS 13920:2016 Cl. 6.2.2 (2.50%)",
            "reason": "Prevents brittle over-reinforced concrete crushing prior to rebar yielding.",
        })

    checks.append({
        "check": "max_tension_steel_pt",
        "value": pt_provided,
        "required_max": pt_max_governing,
        "passed": pt_provided <= pt_max_governing,
        "governing_standard": "IS 13920:2016 Cl. 6.2.2" if seismic_active else "IS 456:2000 Cl. 26.5.1.1(b)",
    })

    # 4. Stirrup Spacing & Plastic Hinge Confinement Zone
    confinement_length_2d = round(2.0 * d, 1)
    max_spacing_is456 = min(round(0.75 * d, 1), 300.0)
    max_spacing_hinge_is13920 = min(round(d / 4.0, 1), round(8.0 * db_min, 1), 100.0)

    if seismic_active:
        conflicts_resolved.append({
            "parameter": "stirrup_spacing_at_support",
            "is456_limit": f"<= {max_spacing_is456} mm (Cl. 26.5.1.5)",
            "is13920_limit": f"<= {max_spacing_hinge_is13920} mm over length 2d = {confinement_length_2d} mm (Cl. 6.3.3)",
            "governing": f"IS 13920:2016 Cl. 6.3.3 ({max_spacing_hinge_is13920} mm)",
            "reason": "Concrete core confinement required in potential plastic hinge regions.",
        })

    checks.append({
        "check": "seismic_confinement_stirrup_spacing",
        "hinge_zone_length_mm": confinement_length_2d if seismic_active else 0.0,
        "max_allowable_hinge_spacing_mm": max_spacing_hinge_is13920 if seismic_active else max_spacing_is456,
        "standard_midspan_max_spacing_mm": min(round(d / 2.0, 1), max_spacing_is456) if seismic_active else max_spacing_is456,
        "governing_standard": "IS 13920:2016 Cl. 6.3.3" if seismic_active else "IS 456:2000 Cl. 26.5.1.5",
    })

    # 5. Hook Details
    hook_angle = 135 if seismic_active else 90
    hook_extension = max(10.0 * stirrup_dia, 65.0) if seismic_active else 8.0 * stirrup_dia
    checks.append({
        "check": "stirrup_hook_detail",
        "hook_angle_deg": hook_angle,
        "extension_length_mm": round(hook_extension, 1),
        "governing_standard": "IS 13920:2016 Cl. 5.2" if seismic_active else "IS 456:2000 Cl. 26.5.1.5",
    })

    all_passed = all(c.get("passed", True) for c in checks)

    return {
        "member_type": "beam",
        "seismic_zone": seismic_zone,
        "seismic_active": seismic_active,
        "status": "COMPLIANT" if all_passed else "NON_COMPLIANT",
        "checks": checks,
        "conflicts_resolved": conflicts_resolved,
        "recommended_hinge_spacing_mm": max_spacing_hinge_is13920 if seismic_active else max_spacing_is456,
        "hinge_zone_length_mm": confinement_length_2d if seismic_active else 0.0,
    }


def resolve_column_seismic_conflicts(
    b: float,
    D: float,
    clear_height: float,
    fck: float,
    fy: float,
    db_min: float,
    tie_dia: float = 8.0,
    seismic_zone: str = "IV",
    is_ductile: bool = True,
) -> Dict[str, Any]:
    """
    Evaluates column lateral tie detailing against IS 456 and IS 13920,
    computing special confining reinforcement length lo and maximum tie pitch.
    """
    seismic_active = is_ductile or seismic_zone.upper() in ["III", "IV", "V"]
    checks: List[Dict[str, Any]] = []
    conflicts_resolved: List[Dict[str, Any]] = []

    # 1. Column Minimum Dimension
    col_min_dim = min(b, D)
    passed_dim = col_min_dim >= 300.0 if seismic_active else col_min_dim >= 200.0

    checks.append({
        "check": "column_minimum_cross_section",
        "value": col_min_dim,
        "required_min": 300.0 if seismic_active else 200.0,
        "passed": passed_dim,
        "governing_standard": "IS 13920:2016 Cl. 7.1.1" if seismic_active else "IS 456:2000 Cl. 26.5.3.1",
    })

    # 2. Confining Zone Length lo (IS 13920 Cl. 7.6.1)
    lo_seismic = max(max(b, D), clear_height / 6.0, 450.0)

    # 3. Tie Pitch in Confining Zone vs IS 456 Standard
    is456_pitch = min(col_min_dim, 16.0 * db_min, 300.0)
    is13920_pitch = min(col_min_dim / 4.0, 6.0 * db_min, 100.0)
    # Pitch shall not be less than 65 mm per IS 13920
    is13920_pitch = max(is13920_pitch, 65.0)

    if seismic_active:
        conflicts_resolved.append({
            "parameter": "lateral_tie_pitch",
            "is456_limit": f"<= {is456_pitch} mm (Cl. 26.5.3.2)",
            "is13920_limit": f"<= {is13920_pitch} mm over lo = {round(lo_seismic, 1)} mm (Cl. 7.6.1)",
            "governing": f"IS 13920:2016 Cl. 7.6.1 ({is13920_pitch} mm)",
            "reason": "Provides concrete core ductility to prevent explosive axial/flexural shear failure.",
        })

    checks.append({
        "check": "confining_tie_pitch",
        "confining_zone_length_lo_mm": round(lo_seismic, 1) if seismic_active else 0.0,
        "max_allowable_confining_pitch_mm": is13920_pitch if seismic_active else is456_pitch,
        "mid_height_pitch_mm": min(col_min_dim / 2.0, is456_pitch) if seismic_active else is456_pitch,
        "governing_standard": "IS 13920:2016 Cl. 7.6.1" if seismic_active else "IS 456:2000 Cl. 26.5.3.2",
    })

    # 4. Tie Hooks (135° mandatory with 10*db extension)
    checks.append({
        "check": "tie_hook_detail",
        "hook_angle_deg": 135 if seismic_active else 90,
        "extension_length_mm": max(10.0 * tie_dia, 65.0) if seismic_active else 8.0 * tie_dia,
        "governing_standard": "IS 13920:2016 Cl. 5.2" if seismic_active else "IS 456:2000",
    })

    return {
        "member_type": "column",
        "seismic_zone": seismic_zone,
        "seismic_active": seismic_active,
        "status": "COMPLIANT" if all(c.get("passed", True) for c in checks) else "NON_COMPLIANT",
        "checks": checks,
        "conflicts_resolved": conflicts_resolved,
        "recommended_confining_pitch_mm": is13920_pitch if seismic_active else is456_pitch,
        "confining_zone_length_lo_mm": round(lo_seismic, 1) if seismic_active else 0.0,
    }
