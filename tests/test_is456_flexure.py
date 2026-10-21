"""
Tests for IS 456 Annex G flexure calculations for singly reinforced rectangular sections.
Validates mu_lim, ast_required_singly, quadratic solving, round-trip checks, and error guards.
Does NOT read .env.
"""

import json
from pathlib import Path
import pytest

from src.validation.is456_flexure import mu_lim, ast_required_singly

ANNEX_G_JSON_PATH = Path("data/processed/is456_annex_g.json")


def test_annex_g_json_structure_and_verified():
    """Checks that is456_annex_g.json loads properly and verified is true."""
    assert ANNEX_G_JSON_PATH.exists(), f"File not found: {ANNEX_G_JSON_PATH}"
    with open(ANNEX_G_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("verified") is True
    assert data.get("code_id") == "IS 456"
    assert data.get("edition_year") == 2000
    assert data.get("annex") == "G"
    assert data.get("clause_reference") == "38.1"
    assert data.get("title") == "Moments of resistance for rectangular and T-sections"
    assert data.get("verified_by") == "Rounaq, manual check against page_109.png"

    items = data.get("items", [])
    assert len(items) == 6
    item_ids = [it["id"] for it in items]
    assert item_ids == ["G-1.1(a)", "G-1.1(b)", "G-1.1(c)", "G-1.1(d)", "G-1.2", "G-2"]


def test_mu_lim_hand_check_value():
    """mu_lim is about 202.9 kNm (2.029e8 N*mm), tolerance 0.1 percent."""
    b = 300.0
    d = 450.0
    fck = 25.0
    fy = 500.0

    calc_mu_lim = mu_lim(b=b, d=d, fck=fck, fy=fy)
    expected_mu_lim = 202.914234e6  # N*mm (approx 202.9 kNm)

    rel_error = abs(calc_mu_lim - expected_mu_lim) / expected_mu_lim
    assert rel_error < 0.001, f"mu_lim error {rel_error:.6f} exceeds 0.1% tolerance"

    mu_lim_kNm = calc_mu_lim / 1e6
    assert abs(mu_lim_kNm - 202.9) < 0.2


def test_ast_required_singly_100_kNm():
    """mu=100 kNm gives Ast about 556.8 mm2 and xu_over_d about 0.199."""
    b = 300.0
    d = 450.0
    fck = 25.0
    fy = 500.0
    mu = 100e6  # 100 kNm in N*mm

    res = ast_required_singly(b=b, d=d, fck=fck, fy=fy, mu=mu)

    assert res["status"] == "ok"
    assert abs(res["ast_mm2"] - 556.8) < 0.5, f"Expected ~556.8 mm2, got {res['ast_mm2']}"
    assert abs(res["xu_over_d"] - 0.199) < 0.005, f"Expected ~0.199, got {res['xu_over_d']}"
    assert "citation" in res
    assert "formula" in res


def test_ast_required_singly_250_kNm_needs_compression_steel():
    """mu=250 kNm gives 'needs_compression_steel' because it exceeds mu_lim (~202.9 kNm)."""
    b = 300.0
    d = 450.0
    fck = 25.0
    fy = 500.0
    mu = 250e6  # 250 kNm in N*mm

    res = ast_required_singly(b=b, d=d, fck=fck, fy=fy, mu=mu)

    assert res["status"] == "needs_compression_steel"
    assert res.get("ast_mm2") is None
    assert "mu_lim" in res


def test_round_trip_g1_1b():
    """Round trip: G-1.1(b) with the returned Ast gives back the input mu within 0.01 percent."""
    b = 300.0
    d = 450.0
    fck = 25.0
    fy = 500.0
    input_mu = 100e6  # N*mm

    res = ast_required_singly(b=b, d=d, fck=fck, fy=fy, mu=input_mu)
    assert res["status"] == "ok"
    ast_provided = res["ast_mm2"]

    # Evaluate G-1.1(b): Mu = 0.87*fy*Ast*d*(1 - Ast*fy/(b*d*fck))
    recalculated_mu = 0.87 * fy * ast_provided * d * (1.0 - (ast_provided * fy) / (b * d * fck))

    rel_diff = abs(recalculated_mu - input_mu) / input_mu
    assert rel_diff < 0.0001, f"Round trip difference {rel_diff:.6f} exceeds 0.01%"


def test_input_validation_errors():
    """fy=550 raises ValueError; b=0 raises ValueError; negative inputs raise ValueError."""
    # Unsupported fy
    with pytest.raises(ValueError):
        mu_lim(300, 450, 25, 550)

    with pytest.raises(ValueError):
        ast_required_singly(300, 450, 25, 550, 100e6)

    # Zero inputs
    with pytest.raises(ValueError):
        mu_lim(0, 450, 25, 500)

    with pytest.raises(ValueError):
        ast_required_singly(0, 450, 25, 500, 100e6)

    with pytest.raises(ValueError):
        ast_required_singly(300, 0, 25, 500, 100e6)

    with pytest.raises(ValueError):
        ast_required_singly(300, 450, 0, 500, 100e6)

    with pytest.raises(ValueError):
        ast_required_singly(300, 450, 25, 500, 0)

    # Negative inputs
    with pytest.raises(ValueError):
        mu_lim(-300, 450, 25, 500)

    with pytest.raises(ValueError):
        ast_required_singly(300, -450, 25, 500, 100e6)

    with pytest.raises(ValueError):
        ast_required_singly(300, 450, 25, 500, -50e6)
