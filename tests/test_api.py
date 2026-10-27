"""
Tests for FastAPI application (src/api/main.py).
Validates authentication, endpoint responses, query validation, and audit logging.
"""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.api.main import app, AUDIT_LOG_FILE

TEST_KEY_NAME = "automated_tester"
TEST_SECRET_KEY = "test_key_secret_xyz_987654"


@pytest.fixture(autouse=True)
def setup_test_api_keys(monkeypatch):
    """Configures test API keys in the environment for all tests."""
    monkeypatch.setenv("IS_RAG_API_KEYS", f"{TEST_KEY_NAME}:{TEST_SECRET_KEY}")


@pytest.fixture
def client():
    """Provides FastAPI TestClient."""
    with TestClient(app) as test_client:
        yield test_client


def test_health_check(client):
    """GET /health returns 200 OK without requiring an API key."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_missing_api_key_returns_401(client):
    """Missing X-API-Key header returns 401 with no detail."""
    response = client.post("/v1/rag/query", json={"query": "nominal cover for moderate exposure"})
    assert response.status_code == 401


def test_wrong_api_key_returns_401(client):
    """Wrong X-API-Key header returns 401 with no detail."""
    response = client.post(
        "/v1/rag/query",
        json={"query": "nominal cover for moderate exposure"},
        headers={"X-API-Key": "completely_invalid_key_value"},
    )
    assert response.status_code == 401


def test_valid_key_returns_200_and_table_16(client):
    """Valid key returns 200 and Table 16 is rank 1 for 'nominal cover for moderate exposure'."""
    response = client.post(
        "/v1/rag/query",
        json={"query": "nominal cover for moderate exposure", "k": 3},
        headers={"X-API-Key": TEST_SECRET_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert "query" in data
    assert "results" in data
    assert "note" in data
    assert len(data["results"]) > 0
    assert data["results"][0]["chunk_id"] == "IS456-2000-TABLE-16"


def test_query_shorter_than_3_chars_returns_422(client):
    """Query shorter than 3 characters returns 422 Unprocessable Entity."""
    response = client.post(
        "/v1/rag/query",
        json={"query": "ab"},
        headers={"X-API-Key": TEST_SECRET_KEY},
    )
    assert response.status_code == 422


def test_audit_log_appended_and_excludes_secret_key(client):
    """Every successful call logs an entry to audit.jsonl, and the secret key is never present."""
    initial_lines = 0
    if AUDIT_LOG_FILE.exists():
        with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
            initial_lines = sum(1 for line in f if line.strip())

    query_text = "minimum shear reinforcement formula for stirrups"
    response = client.post(
        "/v1/rag/query",
        json={"query": query_text, "k": 3},
        headers={"X-API-Key": TEST_SECRET_KEY},
    )
    assert response.status_code == 200

    assert AUDIT_LOG_FILE.exists(), "Audit log file was not created"
    with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    assert len(lines) == initial_lines + 1, "Audit log was not incremented by 1 line"
    last_line = lines[-1]

    # Critical security checks
    assert TEST_SECRET_KEY not in last_line, "Secret API key leaked into audit log!"
    log_data = json.loads(last_line)
    assert log_data["key_name"] == TEST_KEY_NAME
    assert log_data["query"] == query_text
    assert log_data["status_code"] == 200
    assert "returned_chunk_ids" in log_data
    assert "rerank_scores" in log_data
    assert "latency_ms" in log_data


def test_design_assistant_requires_auth(client):
    """POST /v1/design/assistant without API key returns 401."""
    response = client.post("/v1/design/assistant", json={"parameters": {"span_m": 5.0, "dead_load_kN_per_m": 12.0, "live_load_kN_per_m": 8.0}})
    assert response.status_code == 401


def test_design_assistant_direct_parameters_success(client):
    """POST /v1/design/assistant with valid parameters returns deterministic sizing result."""
    params = {
        "span_m": 5.0,
        "dead_load_kN_per_m": 12.0,
        "live_load_kN_per_m": 8.0,
        "fck": 25.0,
        "fy": 500.0,
        "exposure": "Moderate",
    }
    response = client.post(
        "/v1/design/assistant",
        json={"parameters": params},
        headers={"X-API-Key": TEST_SECRET_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "passed"
    assert data["sizing"]["section_dimensions"]["d_actual"] == 402.0
    assert "Passes the implemented IS 456 beam detailing checks only" in data["disclaimer"]


def test_design_assistant_empty_body_returns_422(client):
    """POST /v1/design/assistant with neither query nor parameters returns 422."""
    response = client.post(
        "/v1/design/assistant",
        json={},
        headers={"X-API-Key": TEST_SECRET_KEY},
    )
    assert response.status_code == 422


def test_column_review_endpoint_success(client):
    """POST /v1/design/column/review calculates column and returns 200 OK."""
    response = client.post(
        "/v1/design/column/review",
        json={"axial_load_kN": 1000.0, "length_m": 3.0, "fck": 25.0, "fy": 500.0},
        headers={"X-API-Key": TEST_SECRET_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["section_dimensions"] == "400x400 mm"
    assert data["design_dict"]["rebar_selected"]["bar_count"] in [4, 6, 8]


def test_column_review_endpoint_unauthorized(client):
    """Missing API key returns 401 Unauthorized."""
    response = client.post(
        "/v1/design/column/review",
        json={"axial_load_kN": 1000.0},
    )
    assert response.status_code == 401


def test_column_dxf_endpoint_success(client):
    """POST /v1/design/column/dxf generates column DXF drawing."""
    response = client.post(
        "/v1/design/column/dxf",
        json={"axial_load_kN": 1000.0, "output_filename": "api_test_column.dxf"},
        headers={"X-API-Key": TEST_SECRET_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "api_test_column.dxf" in data["dxf_path"]


def test_slab_review_endpoint_success(client):
    """POST /v1/design/slab/review calculates slab and returns 200 OK."""
    response = client.post(
        "/v1/design/slab/review",
        json={"lx_m": 2.5, "ly_m": 6.0, "live_load_kN_m2": 3.0, "fck": 25.0, "fy": 500.0},
        headers={"X-API-Key": TEST_SECRET_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["slab_type"] == "one_way"
    assert "T" in data["main_reinforcement"]


def test_slab_review_endpoint_unauthorized(client):
    """Missing API key returns 401 Unauthorized for slab endpoint."""
    response = client.post(
        "/v1/design/slab/review",
        json={"lx_m": 2.5, "ly_m": 5.0, "live_load_kN_m2": 3.0},
    )
    assert response.status_code == 401


def test_slab_dxf_endpoint_success(client):
    """POST /v1/design/slab/dxf generates slab CAD drawing."""
    response = client.post(
        "/v1/design/slab/dxf",
        json={"lx_m": 2.5, "ly_m": 5.0, "live_load_kN_m2": 3.0, "output_filename": "api_test_slab.dxf"},
        headers={"X-API-Key": TEST_SECRET_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "api_test_slab.dxf" in data["dxf_path"]


def test_footing_review_endpoint_success(client):
    """POST /v1/design/footing/review calculates footing and returns 200 OK."""
    response = client.post(
        "/v1/design/footing/review",
        json={"axial_load_kN": 1000.0, "sbc_kN_m2": 200.0, "fck": 25.0, "fy": 500.0},
        headers={"X-API-Key": TEST_SECRET_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "mm" in data["plan_dimensions"]
    assert "T" in data["reinforcement_both_ways"]


def test_footing_review_endpoint_unauthorized(client):
    """Missing API key returns 401 Unauthorized for footing endpoint."""
    response = client.post(
        "/v1/design/footing/review",
        json={"axial_load_kN": 1000.0},
    )
    assert response.status_code == 401


def test_footing_dxf_endpoint_success(client):
    """POST /v1/design/footing/dxf generates footing CAD drawing."""
    response = client.post(
        "/v1/design/footing/dxf",
        json={"axial_load_kN": 1000.0, "sbc_kN_m2": 200.0, "output_filename": "api_test_footing.dxf"},
        headers={"X-API-Key": TEST_SECRET_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "api_test_footing.dxf" in data["dxf_path"]


def test_multicode_query_endpoint_success(client):
    """POST /v1/rag/multicode/query searches across multiple standards."""
    response = client.post(
        "/v1/rag/multicode/query",
        json={"query": "minimum grade of concrete in seismic zones", "code": "IS 13920"},
        headers={"X-API-Key": TEST_SECRET_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_results"] > 0
    assert "IS 13920" in data["results"][0]["code"]


def test_multicode_query_endpoint_unauthorized(client):
    """Missing API key returns 401 Unauthorized for multicode query."""
    response = client.post(
        "/v1/rag/multicode/query",
        json={"query": "school classroom live load"},
    )
    assert response.status_code == 401


def test_seismic_compliance_endpoint_beam_success(client):
    """POST /v1/validation/seismic-compliance resolves beam seismic conflicts."""
    response = client.post(
        "/v1/validation/seismic-compliance",
        json={
            "member_type": "beam",
            "b_mm": 250.0,
            "D_mm": 500.0,
            "d_mm": 450.0,
            "fck": 25.0,
            "fy": 500.0,
            "seismic_zone": "IV",
            "is_ductile": True,
        },
        headers={"X-API-Key": TEST_SECRET_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["member_type"] == "beam"
    assert data["seismic_active"] is True
    assert "recommended_hinge_spacing_mm" in data


def test_seismic_compliance_endpoint_unauthorized(client):
    """Missing API key returns 401 Unauthorized for seismic compliance endpoint."""
    response = client.post(
        "/v1/validation/seismic-compliance",
        json={"member_type": "beam", "b_mm": 250.0, "D_mm": 500.0, "fck": 25.0, "fy": 500.0},
    )
    assert response.status_code == 401


def test_seismic_base_shear_endpoint_success(client):
    """POST /v1/design/seismic/base-shear calculates IS 1893 base shear."""
    response = client.post(
        "/v1/design/seismic/base-shear",
        json={
            "height_m": 18.0,
            "total_weight_kN": 12000.0,
            "seismic_zone": "IV",
            "occupancy": "hospital",
            "structural_system": "rc_smrf",
            "soil_type": "medium",
        },
        headers={"X-API-Key": TEST_SECRET_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["seismic_parameters"]["zone_factor_Z"] == 0.24
    assert data["seismic_parameters"]["importance_factor_I"] == 1.5
    assert data["design_base_shear_VB_kN"] > 0


def test_seismic_base_shear_endpoint_unauthorized(client):
    """Missing API key returns 401 Unauthorized for seismic base shear endpoint."""
    response = client.post(
        "/v1/design/seismic/base-shear",
        json={"height_m": 18.0, "total_weight_kN": 12000.0},
    )
    assert response.status_code == 401





