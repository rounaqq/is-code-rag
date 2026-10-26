"""
Unit and integration tests for Step 8: Engineer Review and Feedback Loop module
(src/cad/engineer_review.py and API endpoints).
"""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.generation.beam_sizing import size_beam_from_loads
from src.cad.engineer_review import (
    generate_review_report,
    apply_engineer_overrides,
    sign_off_design,
    export_approved_dxf,
)
from src.api.main import app

TEST_KEY_NAME = "tester"
TEST_SECRET_KEY = "test_key_step8_review_123"


@pytest.fixture(autouse=True)
def setup_api_keys(monkeypatch):
    monkeypatch.setenv("IS_RAG_API_KEYS", f"{TEST_KEY_NAME}:{TEST_SECRET_KEY}")


@pytest.fixture
def sample_sizing():
    return size_beam_from_loads(
        span_m=5.0,
        dead_load_kN_per_m=12.0,
        live_load_kN_per_m=8.0,
        fck=25.0,
        fy=500.0,
        exposure="Moderate",
    )


def test_generate_review_report_structure(sample_sizing):
    """Review report contains all required sections, checks, and assumptions."""
    report = generate_review_report(sample_sizing)

    assert "review_status" in report
    assert "design_summary" in report
    assert "checks" in report
    assert "assumptions" in report
    assert "markdown_report" in report

    # Verify all 8 IS 456 check areas are evaluated
    check_names = [c["check"] for c in report["checks"]]
    assert any("Flexural Capacity" in name for name in check_names)
    assert any("Tension Reinforcement Area" in name for name in check_names)
    assert any("Minimum Horizontal Bar Clear Spacing" in name for name in check_names)
    assert any("Nominal Shear Stress" in name for name in check_names)
    assert any("Shear Reinforcement Spacing" in name for name in check_names)
    assert any("Development Length" in name for name in check_names)
    assert any("Deflection" in name for name in check_names)
    assert any("Nominal Concrete Cover" in name for name in check_names)

    # Check assumptions count
    assert len(report["assumptions"]) >= 5


def test_apply_valid_engineer_overrides(sample_sizing):
    """Engineer can adjust bar diameter and the engine recalculates d_actual and checks."""
    original_design = sample_sizing["design_dict"]
    original_d = original_design["d"]

    # Override: change tension steel to 3-T25 and adjust stirrup spacing
    overrides = {
        "main_bar_dia_mm": 25.0,
        "main_bar_count": 3,
        "stirrup_spacing_mm": 200.0,
    }
    res = apply_engineer_overrides(original_design, overrides)

    assert res["status"] == "override_accepted"
    updated = res["design"]
    assert updated["main_bar_dia_mm"] == 25.0
    assert updated["main_bar_count"] == 3
    # d_actual must have recomputed with larger bar diameter (25/2 vs 20/2)
    assert updated["d"] < original_d
    assert res["review_status"] == "overridden_pending_approval"


def test_apply_invalid_override_spacing_violation(sample_sizing):
    """Overrides violating Cl. 26.3.2 clear bar spacing are rejected."""
    original_design = sample_sizing["design_dict"]

    # Try to pack 8 bars of 25 mm into 230 mm beam width
    overrides = {
        "b": 230.0,
        "main_bar_dia_mm": 25.0,
        "main_bar_count": 8,
    }
    res = apply_engineer_overrides(original_design, overrides)

    assert res["status"] == "override_rejected"
    assert any("clear bar spacing violation" in r for r in res["reasons"])


def test_apply_invalid_override_max_steel_violation(sample_sizing):
    """Overrides exceeding 0.04*b*D are rejected per Cl. 26.5.1.1(b)."""
    original_design = sample_sizing["design_dict"]

    # 10 bars of 32 mm in 200x300 beam
    overrides = {
        "b": 200.0,
        "D": 300.0,
        "main_bar_dia_mm": 32.0,
        "main_bar_count": 10,
    }
    res = apply_engineer_overrides(original_design, overrides)

    assert res["status"] == "override_rejected"
    assert any("maximum tension steel exceeded" in r for r in res["reasons"])


def test_sign_off_design(sample_sizing):
    """Engineer review attaches reviewer metadata."""
    design = sample_sizing["design_dict"]

    with pytest.raises(ValueError):
        sign_off_design(design, "")

    signed = sign_off_design(
        design=design,
        reviewer_name="Er. Sharma",
        reviewer_role="Senior Structural Engineer",
        review_date="2026-10-24",
        outcome="Reviewed",
        remarks="Checked against IS 456 detailing provisions.",
    )

    assert signed["reviewer_name"] == "Er. Sharma"
    assert signed["reviewer_role"] == "Senior Structural Engineer"
    assert signed["review_date"] == "2026-10-24"
    assert signed["outcome"] == "Reviewed"
    assert "Checked against IS 456" in signed["engineer_remarks"]


def test_export_reviewed_and_draft_dxf(sample_sizing, tmp_path):
    """DXF export writes draft drawing by default, or reviewer stamp when supplied."""
    import ezdxf

    design = sample_sizing["design_dict"]
    design["span_m"] = 5.0

    # 1. Default without reviewer -> must say DRAFT
    draft_file = str(tmp_path / "draft_beam.dxf")
    export_approved_dxf(design=design, output_path=draft_file)
    doc_draft = ezdxf.readfile(draft_file)
    draft_texts = [e.dxf.text for e in doc_draft.modelspace().query("TEXT")]
    assert any("STATUS: DRAFT - NOT FOR CONSTRUCTION. Not engineer-reviewed." in t for t in draft_texts)
    assert not any("APPROVED FOR CONSTRUCTION" in t for t in draft_texts)

    # 2. Supplied reviewer name, role and date -> says Reviewed by <name>, <date>: <outcome>
    reviewed_file = str(tmp_path / "reviewed_beam.dxf")
    res = export_approved_dxf(
        design=design,
        output_path=reviewed_file,
        reviewer_name="Er. Verma",
        reviewer_role="Lead Engineer",
        review_date="2026-10-24",
        outcome="Detailing Checked",
    )

    assert res["status"] == "success"
    doc_rev = ezdxf.readfile(reviewed_file)
    rev_texts = [e.dxf.text for e in doc_rev.modelspace().query("TEXT")]
    assert any("Reviewed by Er. Verma, 2026-10-24: Detailing Checked" in t for t in rev_texts)
    assert not any("APPROVED FOR CONSTRUCTION" in t for t in rev_texts)


def test_api_design_review_flow():
    """API endpoint /v1/design/review provides sizing, reports, overrides, and reviewer stamps."""
    with TestClient(app) as client:
        # 1. Generate review report from loads
        resp = client.post(
            "/v1/design/review",
            json={
                "span_m": 4.5,
                "dead_load_kN_per_m": 10.0,
                "live_load_kN_per_m": 6.0,
                "fck": 25.0,
                "fy": 500.0,
            },
            headers={"X-API-Key": TEST_SECRET_KEY},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "review_report" in data
        assert len(data["review_report"]["checks"]) >= 8

        # 2. Apply valid override with reviewer details
        original_design = data["design"]
        resp_override = client.post(
            "/v1/design/review",
            json={
                "design": original_design,
                "overrides": {
                    "main_bar_dia_mm": 20.0,
                    "main_bar_count": 3,
                    "stirrup_spacing_mm": 200.0,
                },
                "reviewer_name": "Er. Patel",
                "reviewer_role": "Chartered Structural Engineer",
                "review_date": "2026-10-24",
                "outcome": "Passed detailing checks",
                "remarks": "Increased bar diameter to 20mm and stirrups to 200mm",
            },
            headers={"X-API-Key": TEST_SECRET_KEY},
        )
        assert resp_override.status_code == 200
        ov_data = resp_override.json()
        assert ov_data["design"]["main_bar_dia_mm"] == 20.0
        assert ov_data["design"]["reviewer_name"] == "Er. Patel"
        assert ov_data["design"]["reviewer_role"] == "Chartered Structural Engineer"
        assert ov_data["design"]["review_date"] == "2026-10-24"
        assert ov_data["design"]["outcome"] == "Passed detailing checks"

        # 3. Test rejection of invalid override
        resp_bad = client.post(
            "/v1/design/review",
            json={
                "design": original_design,
                "overrides": {"main_bar_dia_mm": 32.0, "main_bar_count": 8, "b": 230.0},
            },
            headers={"X-API-Key": TEST_SECRET_KEY},
        )
        assert resp_bad.status_code == 400


def test_api_design_dxf_flow(tmp_path):
    """API endpoint /v1/design/dxf generates and saves DXF with draft status or reviewer stamp."""
    import ezdxf

    with TestClient(app) as client:
        # Default draft DXF
        resp = client.post(
            "/v1/design/dxf",
            json={
                "span_m": 4.0,
                "dead_load_kN_per_m": 10.0,
                "live_load_kN_per_m": 5.0,
                "output_filename": "test_draft_beam.dxf",
            },
            headers={"X-API-Key": TEST_SECRET_KEY},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["dxf_path"] is not None
        assert Path(data["dxf_path"]).exists()

        doc = ezdxf.readfile(data["dxf_path"])
        texts = [e.dxf.text for e in doc.modelspace().query("TEXT")]
        assert any("STATUS: DRAFT - NOT FOR CONSTRUCTION. Not engineer-reviewed." in t for t in texts)
        assert not any("APPROVED FOR CONSTRUCTION" in t for t in texts)
