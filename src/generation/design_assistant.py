"""
IS 456:2000 Structural Design Assistant with LLM Tool Calling.
The LLM functions as the front end:
  1. Reads the engineer's natural language request.
  2. Extracts parameters to call the deterministic sizing tool.
  3. The sizing engine strictly computes all dimensions, steel areas, and spacings.
  4. The LLM writes the engineering explanation citing verified IS 456 clauses.
Does NOT import, read, print, or quote .env or any secret keys.
"""

import json
import math
import re
from typing import Dict, Any, Optional, List, Callable, Union

from src.generation.beam_sizing import size_beam_from_loads, design_and_validate_beam
from src.generation.llm_client import complete_json, generate
from src.generation.design_proposal import _clean_json_text

BASE_DISCLAIMER = (
    "Passes the implemented IS 456 beam detailing checks only; "
    "not a full design check. A structural engineer must review."
)

TOOL_SCHEMA = {
    "name": "size_beam_from_loads",
    "description": (
        "Deterministically sizes a simply supported reinforced concrete rectangular beam per IS 456:2000. "
        "Calculates breadth b, total depth D, actual effective depth d, design moment Mu, shear force Vu, "
        "longitudinal tension rebar Ast, shear stirrups, deflection control check, and development length."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "span_m": {
                "type": "number",
                "description": "Clear span of the beam in metres (strictly positive)",
            },
            "dead_load_kN_per_m": {
                "type": "number",
                "description": "Applied dead load in kN/m excluding self-weight (non-negative)",
            },
            "live_load_kN_per_m": {
                "type": "number",
                "description": "Applied live load in kN/m (non-negative)",
            },
            "fck": {
                "type": "number",
                "description": "Characteristic compressive strength of concrete in N/mm2 (e.g. 20, 25, 30, 35, 40)",
                "default": 25.0,
            },
            "fy": {
                "type": "number",
                "description": "Characteristic yield strength of reinforcement steel in N/mm2 (e.g. 415, 500)",
                "default": 500.0,
            },
            "exposure": {
                "type": "string",
                "enum": ["Mild", "Moderate", "Severe", "Very severe", "Extreme"],
                "description": "Environmental exposure condition per Table 16",
                "default": "Moderate",
            },
            "b": {
                "type": "number",
                "description": "Optional beam width in mm (default 300 mm for spans >= 5m, else 230 mm)",
            },
            "support_width_mm": {
                "type": "number",
                "description": "Width of bearing support in mm",
                "default": 300.0,
            },
            "max_aggregate_size_mm": {
                "type": "number",
                "description": "Nominal maximum size of coarse aggregate in mm per Cl. 26.3.2 (default 20.0)",
                "default": 20.0,
            },
        },
        "required": ["span_m", "dead_load_kN_per_m", "live_load_kN_per_m"],
    },
}

EXTRACTION_SYSTEM_PROMPT = f"""You are an IS 456:2000 structural engineering assistant.
Analyze the user's request and extract the parameters to call the deterministic sizing tool 'size_beam_from_loads'.

Tool definition:
{json.dumps(TOOL_SCHEMA, indent=2)}

Rules:
1. Extract span_m, dead_load_kN_per_m, and live_load_kN_per_m from the text.
2. If fck is specified (e.g. M20 -> 20, M25 -> 25, M30 -> 30), extract it. Default is 25.0.
3. If fy is specified (e.g. Fe 415 -> 415, Fe 500 -> 500), extract it. Default is 500.0.
4. If exposure is specified (Mild, Moderate, Severe, Very severe, Extreme), extract it. Default is "Moderate".
5. If beam width b is explicitly specified, extract it in mm. Otherwise leave null.
6. If span or loads are missing or cannot be determined, set "insufficient_information" to true and list missing fields in "missing_parameters".
7. Never do arithmetic or size the beam yourself. Your only role is to extract tool arguments.

Respond with valid JSON only matching this schema:
{{
  "tool": "size_beam_from_loads",
  "parameters": {{
    "span_m": <float or null>,
    "dead_load_kN_per_m": <float or null>,
    "live_load_kN_per_m": <float or null>,
    "fck": <float>,
    "fy": <float>,
    "exposure": "<string>",
    "b": <float or null>,
    "support_width_mm": <float>,
    "max_aggregate_size_mm": <float>
  }},
  "insufficient_information": <boolean>,
  "missing_parameters": [<list of strings>]
}}"""

EXPLANATION_SYSTEM_PROMPT = """You are a licensed structural engineering design assistant specialized in IS 456:2000.
You are explaining the results of a deterministic beam sizing calculation to a structural engineer.

Strict Rules:
1. Every numerical value (breadth b, total depth D, effective depth d, factored moment Mu, factored shear Vu, rebar count, bar diameter, stirrup spacing, deflection ratio, development length) MUST be copied EXACTLY from the tool output. NEVER alter, recalculate, or guess any number.
2. Explicitly cite the IS 456:2000 clauses for each step:
   - Cl. 19.2.1: Concrete density (25.0 kN/m3 for reinforced concrete) used to calculate beam self-weight
   - Cl. 22.2(a): Effective span calculation
   - Cl. 36.4.1 / Table 18: Partial safety factor 1.5 on loads (wu = 1.5 * (DL + LL))
   - Cl. 38.1 & Annex G-1.1: Limiting flexural capacity and required tension steel Ast
   - Cl. 40, Table 19 & Table 20: Nominal shear stress tau_v, design concrete shear strength tau_c, maximum shear tau_c,max, and stirrups
   - Cl. 23.2.1: Deflection control span-to-depth ratio (basic ratio * modification factor F1; F1 uses an approximate curve fit, not from IS 456)
   - Cl. 26.2.1 & Cl. 26.2.3.3: Development length Ld and support anchorage embedment (Ld / 3)
3. Explicitly state the engineering assumptions:
   - Load factor 1.5 from Table 18
   - Support bearing width default 300 mm
   - Table 19 row rule (row at or below pt without interpolation)
   - Practical stirrup diameter trial sequence (8, 10, 12 mm with 100 mm practical minimum spacing floor)
4. You MUST conclude with the mandatory disclaimer:
   "Passes the implemented IS 456 beam detailing checks only; not a full design check. A structural engineer must review."

Provide a clear, well-structured, professional engineering explanation."""


def parse_engineer_request(
    user_input: Union[str, Dict[str, Any]],
    llm: Optional[Callable[[str, str], str]] = None,
) -> Dict[str, Any]:
    """
    Extracts deterministic sizing tool arguments from an engineer's request.
    If user_input is a dict, extracts parameters directly.
    If user_input is a natural language string, prompts the LLM to extract parameters.
    """
    if isinstance(user_input, dict):
        # Direct dictionary parameters
        span = user_input.get("span_m") or user_input.get("span")
        dl = user_input.get("dead_load_kN_per_m") or user_input.get("dead_load") or user_input.get("dl")
        ll = user_input.get("live_load_kN_per_m") or user_input.get("live_load") or user_input.get("ll")

        missing = []
        if span is None:
            missing.append("span_m")
        if dl is None:
            missing.append("dead_load_kN_per_m")
        if ll is None:
            missing.append("live_load_kN_per_m")

        if missing:
            return {
                "tool": "size_beam_from_loads",
                "parameters": {},
                "insufficient_information": True,
                "missing_parameters": missing,
            }

        agg = user_input.get("max_aggregate_size_mm") or user_input.get("aggregate_size_mm") or user_input.get("aggregate_size")
        return {
            "tool": "size_beam_from_loads",
            "parameters": {
                "span_m": float(span),
                "dead_load_kN_per_m": float(dl),
                "live_load_kN_per_m": float(ll),
                "fck": float(user_input.get("fck", 25.0)),
                "fy": float(user_input.get("fy", 500.0)),
                "exposure": str(user_input.get("exposure", "Moderate")),
                "b": float(user_input["b"]) if user_input.get("b") is not None else None,
                "support_width_mm": float(user_input.get("support_width_mm", 300.0)),
                "max_aggregate_size_mm": float(agg) if agg is not None else 20.0,
            },
            "insufficient_information": False,
            "missing_parameters": [],
        }

    # Natural language string extraction via LLM
    llm_func = llm if llm is not None else complete_json
    raw_output = llm_func(EXTRACTION_SYSTEM_PROMPT, str(user_input))
    cleaned = _clean_json_text(raw_output)

    try:
        parsed = json.loads(cleaned)
    except Exception as exc:
        return {
            "tool": "size_beam_from_loads",
            "parameters": {},
            "insufficient_information": True,
            "missing_parameters": ["span_m", "dead_load_kN_per_m", "live_load_kN_per_m"],
            "error": f"Failed to parse LLM extraction JSON: {exc}",
        }

    # Validate parameters
    params = parsed.get("parameters", {})
    missing = []
    if not params.get("span_m") or float(params["span_m"]) <= 0:
        missing.append("span_m")
    if params.get("dead_load_kN_per_m") is None or float(params["dead_load_kN_per_m"]) < 0:
        missing.append("dead_load_kN_per_m")
    if params.get("live_load_kN_per_m") is None or float(params["live_load_kN_per_m"]) < 0:
        missing.append("live_load_kN_per_m")

    if missing:
        parsed["insufficient_information"] = True
        parsed["missing_parameters"] = missing
    else:
        parsed["insufficient_information"] = bool(parsed.get("insufficient_information", False))
        parsed["missing_parameters"] = parsed.get("missing_parameters", [])

    return parsed


def execute_sizing_tool(tool_parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes the deterministic IS 456 sizing and validation pipeline.
    The code stays in charge of every number.
    """
    res = design_and_validate_beam(
        span_m=float(tool_parameters["span_m"]),
        dead_load_kN_per_m=float(tool_parameters["dead_load_kN_per_m"]),
        live_load_kN_per_m=float(tool_parameters["live_load_kN_per_m"]),
        fck=float(tool_parameters.get("fck", 25.0)),
        fy=float(tool_parameters.get("fy", 500.0)),
        exposure=str(tool_parameters.get("exposure", "Moderate")),
        b=tool_parameters.get("b"),
        support_width_mm=float(tool_parameters.get("support_width_mm", 300.0)),
        max_aggregate_size_mm=float(tool_parameters.get("max_aggregate_size_mm", 20.0)),
    )
    return res


def generate_design_explanation(
    user_query: str,
    sizing_result: Dict[str, Any],
    llm: Optional[Callable[[str, str], str]] = None,
) -> str:
    """
    Prompts the LLM to write a comprehensive engineering explanation of the deterministic sizing result.
    """
    sizing = sizing_result.get("sizing", {})
    status = sizing_result.get("status")

    if status == "needs_review":
        reason = sizing_result.get("reason", "Structural review required")
        prompt = (
            f"The engineer asked:\n\"{user_query}\"\n\n"
            f"The deterministic sizing calculation could not finalize the section because:\n{reason}\n\n"
            f"Calculation details:\n{json.dumps(sizing, indent=2)}\n\n"
            f"Explain clearly to the engineer why the design requires review and what cross-sectional adjustments "
            f"(such as increasing breadth b or depth D) are recommended per IS 456:2000. Include the disclaimer."
        )
    else:
        dims = sizing.get("section_dimensions", {})
        rebar = sizing.get("reinforcement_detailing", {})
        loads = sizing.get("derived_loads", {})
        shear = sizing.get("shear", {})
        flex = sizing.get("flexure", {})
        defl = sizing.get("deflection", {})
        ld = sizing.get("development_length", {})

        prompt = f"""Engineer Request:
"{user_query}"

Deterministic IS 456 Calculation Results:
- Cross-Section Dimensions: b = {dims.get('b')} mm, D = {dims.get('D')} mm, d_actual = {dims.get('d_actual')} mm, nominal cover = {dims.get('cover_mm')} mm
- Derived Loads & Moments:
  - Self-weight = {loads.get('self_weight_kN_per_m')} kN/m (unit weight = 25.0 kN/m3 per Cl. 19.2.1)
  - Effective span = {loads.get('effective_span_m')} m (Cl. 22.2(a))
  - Factored load wu = {loads.get('factored_load_wu_kN_per_m')} kN/m (1.5 load factor per Cl. 36.4.1 / Table 18)
  - Factored Moment Mu = {loads.get('factored_moment_Mu_kNm')} kNm
  - Factored Shear Force Vu = {loads.get('factored_shear_Vu_kN')} kN
- Flexural Reinforcement:
  - Required Ast = {flex.get('ast_design_mm2')} mm2 (Cl. 38.1 & Annex G-1.1)
  - Limiting flexural capacity Mu,lim = {flex.get('mu_lim_kNm')} kNm (xu/d = {flex.get('xu_over_d')})
  - Provided bottom tension bars: {rebar.get('main_bar_count')} bars of diameter {rebar.get('main_bar_dia_mm')} mm (Area = {rebar.get('main_bar_area_provided_mm2')} mm2)
  - Provided top hanger bars: {rebar.get('compression_bar_count')} bars of diameter {rebar.get('compression_bar_dia_mm')} mm
- Shear Reinforcement:
  - Nominal shear stress tau_v = {shear.get('nominal_shear_stress_tau_v')} N/mm2 (Cl. 40.1)
  - Design concrete shear strength tau_c = {shear.get('tau_c')} N/mm2 (Table 19)
  - Maximum shear stress tau_c,max = {shear.get('tau_c_max')} N/mm2 (Table 20)
  - Provided stirrups: 2-legged {rebar.get('stirrup_dia_mm')} mm diameter @ {rebar.get('stirrup_spacing_mm')} mm c/c (Status: {shear.get('shear_status')})
- Deflection Control:
  - Actual span-to-effective-depth ratio L/d = {defl.get('actual_ld_ratio')} <= Allowable {defl.get('max_ld_ratio')} (Status: {defl.get('status')}, Basic ratio = {defl.get('basic_ratio')}, Modification factor F1 = {defl.get('modification_factor_f1')} [unclamped: {defl.get('modification_factor_f1_unclamped')}], Cl. 23.2.1; F1 is an approximate curve fit, not from IS 456; Fig. 4 has not yet been entered from the page; deflection result is indicative only)
- Development Length:
  - Ld = {ld.get('ld_rounded_mm')} mm (approx {ld.get('bar_diameters_multiple')} phi) per Cl. 26.2.1
  - Minimum support anchorage embedment (Ld / 3) = {ld.get('support_anchorage_min_mm')} mm per Cl. 26.2.3.3

Explain these exact results to the structural engineer with all clause citations, stated assumptions, and the mandatory disclaimer."""

    llm_func = llm if llm is not None else generate
    try:
        try:
            explanation = llm_func(prompt=prompt, system_prompt=EXPLANATION_SYSTEM_PROMPT)
        except TypeError:
            # Fallback if llm function signature is (system, user)
            explanation = llm_func(EXPLANATION_SYSTEM_PROMPT, prompt)
    except Exception as exc:
        # Graceful fallback when remote LLM service is offline / unreachable
        if status == "needs_review":
            explanation = (
                f"Design Status: Needs Review.\n"
                f"The deterministic sizing calculation could not finalize the section: {sizing_result.get('reason')}\n"
                f"Adjust section dimensions (breadth b or depth D) per IS 456:2000.\n\n"
                f"{BASE_DISCLAIMER}"
            )
        else:
            explanation = (
                f"Deterministic IS 456:2000 RC Beam Design Summary:\n"
                f"- Cross-Section: {int(dims.get('b', 0))} mm width x {int(dims.get('D', 0))} mm overall depth "
                f"(actual effective depth d = {dims.get('d_actual')} mm, nominal cover = {dims.get('cover_mm')} mm per Table 16).\n"
                f"- Loads & Moments: Self-weight = {loads.get('self_weight_kN_per_m')} kN/m (unit weight 25.0 kN/m3 per Cl. 19.2.1), "
                f"Effective span = {loads.get('effective_span_m')} m per Cl. 22.2(a), "
                f"Factored load wu = {loads.get('factored_load_wu_kN_per_m')} kN/m (1.5 load factor per Cl. 36.4.1 / Table 18), "
                f"Factored Moment Mu = {loads.get('factored_moment_Mu_kNm')} kNm, Factored Shear Vu = {loads.get('factored_shear_Vu_kN')} kN.\n"
                f"- Flexural Steel: Required Ast = {flex.get('ast_design_mm2')} mm2 (Cl. 38.1 & Annex G-1.1). "
                f"Provided bottom tension reinforcement: {rebar.get('main_bar_count')} bars of diameter {int(rebar.get('main_bar_dia_mm', 0))} mm "
                f"({rebar.get('main_bar_area_provided_mm2')} mm2). Provided top hanger bars: {rebar.get('compression_bar_count')} bars of diameter {int(rebar.get('compression_bar_dia_mm', 0))} mm.\n"
                f"- Shear Reinforcement: Nominal shear stress tau_v = {shear.get('nominal_shear_stress_tau_v')} N/mm2 (Cl. 40.1), "
                f"Concrete shear strength tau_c = {shear.get('tau_c')} N/mm2 (Table 19), tau_c,max = {shear.get('tau_c_max')} N/mm2 (Table 20). "
                f"Provided stirrups: 2-legged {int(rebar.get('stirrup_dia_mm', 0))} mm diameter @ {int(rebar.get('stirrup_spacing_mm', 0))} mm c/c "
                f"(Status: {shear.get('shear_status')}).\n"
                f"- Deflection Control: Span/effective-depth ratio L/d = {defl.get('actual_ld_ratio')} <= allowable {defl.get('max_ld_ratio')} "
                f"per Cl. 23.2.1 (Status: {defl.get('status')}; F1 uses an approximate curve fit, not from IS 456; Fig. 4 has not yet been entered from the page; deflection result is indicative only).\n"
                f"- Development Length: Ld = {ld.get('ld_rounded_mm')} mm per Cl. 26.2.1, support anchorage embedment (Ld / 3) = {ld.get('support_anchorage_min_mm')} mm per Cl. 26.2.3.3.\n\n"
                f"{BASE_DISCLAIMER}"
            )

    # Ensure disclaimer is present
    if BASE_DISCLAIMER not in explanation:
        explanation = f"{explanation.strip()}\n\n---\n**Disclaimer**: {BASE_DISCLAIMER}"

    return explanation


def verify_explanation_consistency(explanation: str, sizing_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verifies that the LLM explanation faithfully reflects the deterministic numbers.
    Checks that breadth, depth, bar count, bar diameter, and stirrup spacing match.
    """
    sizing = sizing_result.get("sizing", {})
    if not sizing:
        return {"consistent": True, "discrepancies": []}

    dims = sizing.get("section_dimensions", {})
    rebar = sizing.get("reinforcement_detailing", {})
    discrepancies = []

    b = dims.get("b")
    D = dims.get("D")
    bar_dia = rebar.get("main_bar_dia_mm")
    bar_cnt = rebar.get("main_bar_count")
    spacing = rebar.get("stirrup_spacing_mm")

    # Simple regex presence checks for key structural dimensions
    if b is not None and str(int(b)) not in explanation:
        discrepancies.append(f"Width b={int(b)} mm not mentioned in explanation")
    if D is not None and str(int(D)) not in explanation:
        discrepancies.append(f"Depth D={int(D)} mm not mentioned in explanation")
    if bar_dia is not None and str(int(bar_dia)) not in explanation:
        discrepancies.append(f"Main bar diameter {int(bar_dia)} mm not mentioned in explanation")
    if spacing is not None and str(int(spacing)) not in explanation:
        discrepancies.append(f"Stirrup spacing {int(spacing)} mm not mentioned in explanation")

    return {
        "consistent": len(discrepancies) == 0,
        "discrepancies": discrepancies,
    }


def design_beam_assistant(
    user_input: Union[str, Dict[str, Any]],
    llm_extractor: Optional[Callable[[str, str], str]] = None,
    llm_explainer: Optional[Callable[[str, str], str]] = None,
) -> Dict[str, Any]:
    """
    End-to-End LLM Front-End Workflow for IS 456 RC Beam Design:
      1. Reads the engineer's request.
      2. LLM extracts tool parameters (`size_beam_from_loads`).
      3. Deterministic Python engine computes all numbers (b, D, d, Mu, Vu, rebar, shear, deflection, Ld).
      4. Deterministic code validation verifies IS 456 detailing compliance.
      5. LLM writes an engineering explanation with verified clause citations.
      6. Verifies numerical consistency and attaches engineering disclaimer.

    The code stays in charge of every number.
    """
    query_str = json.dumps(user_input) if isinstance(user_input, dict) else str(user_input)

    # 1. Parameter extraction
    tool_call = parse_engineer_request(user_input, llm=llm_extractor)

    if tool_call.get("insufficient_information"):
        missing = tool_call.get("missing_parameters", [])
        missing_str = ", ".join(missing) if missing else "required design parameters"
        message = (
            f"Insufficient information to size the beam. Please provide the missing parameters: {missing_str}. "
            f"A beam design requires clear span (span_m), applied dead load (dead_load_kN_per_m), and "
            f"applied live load (live_load_kN_per_m)."
        )
        return {
            "status": "insufficient_information",
            "query": query_str,
            "tool_call": tool_call,
            "sizing": None,
            "validation": None,
            "explanation": f"{message}\n\n---\n**Disclaimer**: {BASE_DISCLAIMER}",
            "disclaimer": BASE_DISCLAIMER,
        }

    # 2. Tool Execution (plain code calculates)
    params = tool_call["parameters"]
    sizing_res = execute_sizing_tool(params)

    # 3. LLM Explanation with Citations
    explanation = generate_design_explanation(
        user_query=query_str,
        sizing_result=sizing_res,
        llm=llm_explainer,
    )

    # 4. Consistency check
    consistency = verify_explanation_consistency(explanation, sizing_res)

    sizing = sizing_res.get("sizing")
    validation = sizing_res.get("validation")
    status = sizing_res.get("status", "ok")

    return {
        "status": status,
        "query": query_str,
        "tool_call": tool_call,
        "sizing": sizing,
        "validation": validation,
        "shear_status": sizing_res.get("shear_status"),
        "explanation": explanation,
        "consistency_check": consistency,
        "is456_citations": sizing.get("is456_citations", []) if sizing else [],
        "notes": sizing.get("notes", []) if sizing else [],
        "disclaimer": BASE_DISCLAIMER,
    }
