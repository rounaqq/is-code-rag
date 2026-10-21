"""
Tests for IS 456 beam preliminary sizing and load-based design engine (src/generation/beam_sizing.py).
Validates cross-sectional dimensioning, load factors, Annex G flexure, shear checks,
and full end-to-end validation from Span & Load inputs.
Does NOT read .env or call any external network services.
"""

import pytest
from src.generation.beam_sizing import (
    size_beam_from_loads,
    select_practical_tension_bars,
    design_and_validate_beam,
)


def test_select_practical_tension_bars():
    """Tension bar selection gives adequate area and valid clearance."""
    dia, count, area = select_practical_tension_bars(
        b=300.0,
        ast_required=800.0,
        cover_mm=30.0,
        stirrup_dia=8.0,
    )
    assert area >= 800.0
    assert count >= 2
    assert dia in [12.0, 16.0, 20.0, 25.0, 32.0]

    # Verify bars fit across beam width with clearance
    clear_width = 300.0 - 2.0 * 30.0 - 2.0 * 8.0 - (count * dia)
    clear_spacing = clear_width / (count - 1)
    assert clear_spacing >= min(dia, 20.0)


def test_size_beam_from_loads_5m_typical():
    """A typical 5.0m span residential beam with moderate loads."""
    res = size_beam_from_loads(
        span_m=5.0,
        dead_load_kN_per_m=12.0,
        live_load_kN_per_m=8.0,
        fck=25.0,
        fy=500.0,
        exposure="Moderate",
    )

    # 1. Check section dimensions
    dims = res["section_dimensions"]
    assert dims["b"] in [230.0, 300.0]
    assert dims["d"] >= 300.0  # Reasonable effective depth for 5m span
    assert dims["D"] > dims["d"]
    assert dims["cover_mm"] == 30.0  # Table 16 Moderate cover

    # 2. Check derived loads and forces
    derived = res["derived_loads"]
    assert derived["self_weight_kN_per_m"] > 0
    assert derived["factored_load_wu_kN_per_m"] > 30.0  # 1.5 * (12 + 8 + self_weight)
    assert derived["factored_moment_Mu_kNm"] > 0
    assert derived["factored_shear_Vu_kN"] > 0
    assert derived["effective_span_m"] >= 5.0

    # 3. Check flexure and steel limits
    flex = res["flexure"]
    assert flex["ast_design_mm2"] >= flex["ast_min_mm2"]
    assert flex["ast_design_mm2"] <= flex["ast_max_mm2"]
    assert flex["xu_over_d"] <= 0.46  # Below Cl. 38.1 limiting value for Fe 500

    # 4. Check shear stress
    shear = res["shear"]
    assert shear["nominal_shear_stress_tau_v"] <= shear["tau_c_max"]
    assert shear["shear_safe"] is True

    # 5. Check reinforcement detailing
    rebar = res["reinforcement_detailing"]
    assert rebar["main_bar_count"] >= 2
    assert rebar["main_bar_area_provided_mm2"] >= flex["ast_design_mm2"]
    assert rebar["compression_bar_count"] == 2
    assert rebar["stirrup_dia_mm"] == 8.0
    assert rebar["stirrup_spacing_mm"] <= 300.0


def test_design_and_validate_beam_end_to_end():
    """End-to-end design from loads passes all deterministic IS 456 checks."""
    result = design_and_validate_beam(
        span_m=4.5,
        dead_load_kN_per_m=10.0,
        live_load_kN_per_m=6.0,
        fck=20.0,
        fy=415.0,
        exposure="Mild",
    )

    assert result["status"] == "passed"
    val = result["validation"]
    assert val["status"] == "passed"
    assert val["cover_mm"] == 20.0  # Mild exposure from Table 16
    assert len(val["checks"]) >= 5
    assert all(chk["passed"] for chk in val["checks"])

    # Ensure all citations and clause texts are attached
    for chk in val["checks"]:
        assert "citation" in chk
        assert "chunk_id" in chk
        assert "clause_text" in chk
        assert len(chk["clause_text"]) > 0


def test_beam_sizing_input_validations():
    """Invalid spans, loads, and material values raise ValueError."""
    # Zero or negative span
    with pytest.raises(ValueError, match="Span must be strictly positive"):
        size_beam_from_loads(span_m=0, dead_load_kN_per_m=10, live_load_kN_per_m=5)

    with pytest.raises(ValueError, match="Span must be strictly positive"):
        size_beam_from_loads(span_m=-4.0, dead_load_kN_per_m=10, live_load_kN_per_m=5)

    # Zero total load
    with pytest.raises(ValueError, match="Total applied service load must be greater than zero"):
        size_beam_from_loads(span_m=5.0, dead_load_kN_per_m=0, live_load_kN_per_m=0)

    # Negative load
    with pytest.raises(ValueError, match="Applied dead and live loads must be non-negative"):
        size_beam_from_loads(span_m=5.0, dead_load_kN_per_m=-5.0, live_load_kN_per_m=10)

    # Negative width
    with pytest.raises(ValueError, match="Beam width b must be positive"):
        size_beam_from_loads(span_m=5.0, dead_load_kN_per_m=10, live_load_kN_per_m=5, b=-230)


def test_propose_with_span_and_loads():
    """propose() can accept span_m and load without b, D, d and successfully auto-sizes."""
    import json
    import re
    from src.generation.design_proposal import propose

    def fake_llm(system: str, user: str) -> str:
        # Verify user prompt received auto-sized dimensions
        assert "Breadth (b): 230" in user or "Breadth (b): 300" in user
        match = re.search(r"Chunk ID:\s*([A-Za-z0-9\-().]+)", user)
        cid = match.group(1) if match else "IS456-2000-CL-26.5.1.1(a)"
        return json.dumps({
            "main_bar_dia_mm": 16,
            "main_bar_count": 3,
            "stirrup_dia_mm": 8,
            "stirrup_spacing_mm": 150,
            "compression_bar_dia_mm": 10,
            "compression_bar_count": 2,
            "citations": [cid],
            "reasoning": "Reinforcement detailing based on auto-sized beam geometry.",
            "insufficient_information": False,
        })

    req = {
        "span_m": 4.0,
        "dead_load_kN_per_m": 12.0,
        "live_load_kN_per_m": 8.0,
        "fck": 25,
        "fy": 500,
        "exposure": "Moderate",
        "question": "propose beam reinforcement for 4m span",
    }
    res = propose(req, llm=fake_llm)
    assert res["status"] == "accepted"
    assert res["cover_mm"] == 30
    assert len(res["checks"]) > 0
    assert all(chk["passed"] for chk in res["checks"])


def test_beam_sizing_small_shear_minimum_steel_ok():
    """Beam with low shear (tau_v <= tau_c) receives shear_status = 'minimum_shear_steel'."""
    res = size_beam_from_loads(
        span_m=2.0,
        dead_load_kN_per_m=2.0,
        live_load_kN_per_m=1.0,
        fck=30.0,
        fy=500.0,
        exposure="Moderate",
    )
    assert res["shear_status"] in ("minimum_shear_steel", "minimum_shear_steel_ok")
    assert res["shear"]["shear_status"] in ("minimum_shear_steel", "minimum_shear_steel_ok")
    assert res["design_dict"]["shear_status"] in ("minimum_shear_steel", "minimum_shear_steel_ok")
    assert res["shear"]["nominal_shear_stress_tau_v"] <= res["shear"]["tau_c"]
    assert any("assumption" in n.lower() for n in res["shear"]["notes"])


def test_beam_sizing_large_shear_stirrups_designed():
    """Beam with high shear (tau_v > tau_c) designs stirrups and receives shear_status = 'stirrups_designed'."""
    res = size_beam_from_loads(
        span_m=5.0,
        dead_load_kN_per_m=15.0,
        live_load_kN_per_m=10.0,
        fck=25.0,
        fy=500.0,
        exposure="Moderate",
    )
    assert res["shear_status"] == "stirrups_designed"
    assert res["shear"]["shear_status"] == "stirrups_designed"
    assert res["design_dict"]["shear_status"] == "stirrups_designed"
    assert res["shear"]["nominal_shear_stress_tau_v"] > res["shear"]["tau_c"]
    assert res["shear"]["vus"] is not None and res["shear"]["vus"] > 0


def test_shear_design_high_vs_low_shear_spacing():
    """A beam with high shear gives a smaller spacing than the same beam with low shear and status 'stirrups_designed'."""
    # Compare identical beam spans, dimensions, and materials with high vs low load
    res_high = size_beam_from_loads(
        span_m=5.0,
        dead_load_kN_per_m=20.0,
        live_load_kN_per_m=15.0,
        fck=25.0,
        fy=500.0,
        exposure="Moderate",
        b=300.0,
    )
    res_low = size_beam_from_loads(
        span_m=5.0,
        dead_load_kN_per_m=4.0,
        live_load_kN_per_m=2.0,
        fck=25.0,
        fy=500.0,
        exposure="Moderate",
        b=300.0,
    )

    assert res_high["shear_status"] == "stirrups_designed"
    spacing_high = res_high["reinforcement_detailing"]["stirrup_spacing_mm"]
    spacing_low = res_low["reinforcement_detailing"]["stirrup_spacing_mm"]
    assert spacing_high < spacing_low, f"High shear spacing {spacing_high} should be smaller than low shear spacing {spacing_low}"


def test_shear_design_section_too_small_returns_needs_review():
    """Beam with extreme shear exceeding tau_c_max returns status 'needs_review'."""
    # An extreme load on a small section causing tau_v > tau_c_max
    res = size_beam_from_loads(
        span_m=6.0,
        dead_load_kN_per_m=150.0,
        live_load_kN_per_m=100.0,
        fck=20.0,
        fy=415.0,
        exposure="Mild",
        b=230.0,
    )
    # tau_c_max for M20 is 2.8 N/mm2. For 6m span with wu ~ 400 kN/m, Vu ~ 1200 kN,
    assert res["status"] == "needs_review"
    assert "section_too_small" in res["reason"]



