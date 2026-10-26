"""
Tests for IS 456 Structural Design Assistant with LLM Tool Calling (src/generation/design_assistant.py).
Validates parameter extraction, deterministic tool execution, explanation generation,
disclaimer enforcement, and safety guards.
Does NOT call external networks or read .env.
"""

import json
import pytest

from src.generation.design_assistant import (
    TOOL_SCHEMA,
    BASE_DISCLAIMER,
    parse_engineer_request,
    execute_sizing_tool,
    generate_design_explanation,
    verify_explanation_consistency,
    design_beam_assistant,
)


def test_tool_schema_definition():
    """Verify tool schema matches expected IS 456 sizing parameters."""
    assert TOOL_SCHEMA["name"] == "size_beam_from_loads"
    assert "parameters" in TOOL_SCHEMA
    props = TOOL_SCHEMA["parameters"]["properties"]
    assert "span_m" in props
    assert "dead_load_kN_per_m" in props
    assert "live_load_kN_per_m" in props
    assert "fck" in props
    assert "fy" in props
    assert "exposure" in props


def test_parse_engineer_request_from_dict():
    """Direct dictionary input extracts parameters without LLM invocation."""
    req_dict = {
        "span_m": 5.0,
        "dead_load_kN_per_m": 12.0,
        "live_load_kN_per_m": 8.0,
        "fck": 25.0,
        "fy": 500.0,
        "exposure": "Moderate",
    }
    parsed = parse_engineer_request(req_dict)
    assert parsed["insufficient_information"] is False
    assert parsed["missing_parameters"] == []
    params = parsed["parameters"]
    assert params["span_m"] == 5.0
    assert params["dead_load_kN_per_m"] == 12.0
    assert params["live_load_kN_per_m"] == 8.0
    assert params["fck"] == 25.0
    assert params["fy"] == 500.0
    assert params["exposure"] == "Moderate"


def test_parse_engineer_request_from_dict_missing_fields():
    """Dictionary missing span or live load flags insufficient information."""
    incomplete = {"span_m": 5.0, "dead_load_kN_per_m": 10.0}
    parsed = parse_engineer_request(incomplete)
    assert parsed["insufficient_information"] is True
    assert "live_load_kN_per_m" in parsed["missing_parameters"]


def test_parse_engineer_request_from_natural_language_llm():
    """Natural language request uses LLM to extract structured tool call."""
    def fake_extractor(system: str, user: str) -> str:
        assert "5.0 m" in user or "5m" in user or "span" in user
        return json.dumps({
            "tool": "size_beam_from_loads",
            "parameters": {
                "span_m": 5.0,
                "dead_load_kN_per_m": 12.0,
                "live_load_kN_per_m": 8.0,
                "fck": 25.0,
                "fy": 500.0,
                "exposure": "Moderate",
                "b": None,
                "support_width_mm": 300.0,
            },
            "insufficient_information": False,
            "missing_parameters": [],
        })

    query = "Design a simply supported rectangular beam of 5.0 m clear span with dead load 12 kN/m and live load 8 kN/m using M25 concrete and Fe500 steel under moderate exposure."
    parsed = parse_engineer_request(query, llm=fake_extractor)

    assert parsed["insufficient_information"] is False
    assert parsed["parameters"]["span_m"] == 5.0
    assert parsed["parameters"]["dead_load_kN_per_m"] == 12.0
    assert parsed["parameters"]["live_load_kN_per_m"] == 8.0


def test_execute_sizing_tool_deterministic():
    """Deterministic tool execution computes b, D, actual d, forces, and checks."""
    params = {
        "span_m": 5.0,
        "dead_load_kN_per_m": 12.0,
        "live_load_kN_per_m": 8.0,
        "fck": 25.0,
        "fy": 500.0,
        "exposure": "Moderate",
    }
    result = execute_sizing_tool(params)
    assert result["status"] == "passed"
    sizing = result["sizing"]
    dims = sizing["section_dimensions"]
    assert dims["b"] in [230.0, 300.0]
    assert dims["D"] > dims["d"]
    assert dims["d"] == dims["d_actual"]

    # Verify Cl. 23.2 deflection and Cl. 26.2 development length
    assert "deflection" in sizing
    assert sizing["deflection"]["status"] == "indicative"
    assert sizing["deflection"]["ratio_satisfied"] is True
    assert "development_length" in sizing
    assert sizing["development_length"]["ld_mm"] > 0


def test_design_beam_assistant_end_to_end_passed():
    """Full assistant workflow: Query -> Tool Call -> Sizing -> Verification -> Explanation."""
    def fake_extractor(system: str, user: str) -> str:
        return json.dumps({
            "tool": "size_beam_from_loads",
            "parameters": {
                "span_m": 5.0,
                "dead_load_kN_per_m": 12.0,
                "live_load_kN_per_m": 8.0,
                "fck": 25.0,
                "fy": 500.0,
                "exposure": "Moderate",
                "b": 300.0,
                "support_width_mm": 300.0,
            },
            "insufficient_information": False,
            "missing_parameters": [],
        })

    def fake_explainer(system: str, user: str) -> str:
        return (
            "The simply supported beam is designed as a 300 x 450 mm section with actual effective depth d = 402 mm. "
            "Flexural reinforcement consists of 3-T20 mm bottom bars (Cl. 38.1 & Annex G). "
            "Shear stirrups are 2-legged 8 mm diameter @ 300 mm c/c complying with Cl. 40 and Cl. 26.5.1.5. "
            "Deflection control is indicative per Cl. 23.2.1 (actual L/d = 12.44 <= allowable 20.32; F1 approximate curve fit, not from IS 456). "
            "Development length Ld = 888 mm per Cl. 26.2.1.\n\n"
            f"{BASE_DISCLAIMER}"
        )

    query = "Please size a beam for 5m span with 12 kN/m DL and 8 kN/m LL, M25 concrete, Fe500 steel, moderate exposure."
    res = design_beam_assistant(query, llm_extractor=fake_extractor, llm_explainer=fake_explainer)

    assert res["status"] == "passed"
    assert res["sizing"] is not None
    assert res["validation"]["status"] == "passed"
    assert res["sizing"]["section_dimensions"]["d_actual"] == 402.0
    assert "3-T20" in res["explanation"] or "300" in res["explanation"]
    assert BASE_DISCLAIMER in res["explanation"]
    assert res["consistency_check"]["consistent"] is True


def test_design_beam_assistant_insufficient_information():
    """Vague query returns status 'insufficient_information' and guides engineer."""
    def fake_extractor(system: str, user: str) -> str:
        return json.dumps({
            "tool": "size_beam_from_loads",
            "parameters": {},
            "insufficient_information": True,
            "missing_parameters": ["span_m", "dead_load_kN_per_m", "live_load_kN_per_m"],
        })

    res = design_beam_assistant("Can you design a beam for me?", llm_extractor=fake_extractor)
    assert res["status"] == "insufficient_information"
    assert res["sizing"] is None
    assert "span_m" in res["explanation"]
    assert BASE_DISCLAIMER in res["explanation"]


def test_design_beam_assistant_needs_review_when_section_too_small():
    """Extreme loads exceeding tau_c_max halt design and return needs_review explanation."""
    req_dict = {
        "span_m": 6.0,
        "dead_load_kN_per_m": 150.0,
        "live_load_kN_per_m": 100.0,
        "fck": 20.0,
        "fy": 415.0,
        "exposure": "Mild",
        "b": 230.0,
    }

    def fake_explainer(system: str, user: str) -> str:
        return f"Section too small: nominal shear stress exceeds tau_c_max. Dimensions must be increased.\n\n{BASE_DISCLAIMER}"

    res = design_beam_assistant(req_dict, llm_explainer=fake_explainer)
    assert res["status"] == "needs_review"
    assert "section_too_small" in res["sizing"]["reason"]
    assert BASE_DISCLAIMER in res["explanation"]


def test_design_beam_assistant_fallback_when_llm_offline():
    """When LLM service raises an error or is offline, assistant provides deterministic fallback explanation."""
    def offline_llm(system: str, user: str) -> str:
        raise RuntimeError("connection error")

    req = {
        "span_m": 5.0,
        "dead_load_kN_per_m": 12.0,
        "live_load_kN_per_m": 8.0,
        "fck": 25.0,
        "fy": 500.0,
        "exposure": "Moderate",
        "b": 300.0,
    }
    res = design_beam_assistant(req, llm_explainer=offline_llm)
    assert res["status"] == "passed"
    assert "Deterministic IS 456:2000 RC Beam Design Summary" in res["explanation"]
    assert BASE_DISCLAIMER in res["explanation"]
    assert res["consistency_check"]["consistent"] is True

