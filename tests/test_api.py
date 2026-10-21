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
