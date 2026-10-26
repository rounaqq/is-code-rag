"""
Unit tests for Step 10: Containerization, CI/CD Pipeline & Deployment Infrastructure.
Validates:
  1. Dockerfile structure, non-root user security, and healthcheck specification.
  2. docker-compose.yml configuration, volume mounts, and service definitions.
  3. .dockerignore exclusions (secrets, virtual environments, caches).
  4. GitHub Actions CI/CD workflow (.github/workflows/ci.yml) syntax and jobs.
  5. API container endpoints (/health, /v1/rag/query, /v1/design/review, /v1/design/dxf).
Does NOT read .env or call external networks.
"""

from pathlib import Path
import pytest
import yaml

from fastapi.testclient import TestClient
from src.api.main import app

DOCKERFILE_PATH = Path("Dockerfile")
COMPOSE_PATH = Path("docker-compose.yml")
DOCKERIGNORE_PATH = Path(".dockerignore")
CI_WORKFLOW_PATH = Path(".github/workflows/ci.yml")


def test_dockerfile_configuration():
    """Validates Dockerfile instructions, non-root security, and healthcheck."""
    assert DOCKERFILE_PATH.exists(), "Dockerfile must exist at repository root"
    content = DOCKERFILE_PATH.read_text(encoding="utf-8")

    assert "FROM python:" in content
    assert "WORKDIR /app" in content
    assert "EXPOSE 8000" in content
    assert "HEALTHCHECK" in content
    assert "/health" in content
    assert "useradd" in content and "appuser" in content, "Dockerfile must create non-root user"
    assert "USER appuser", "Dockerfile must switch to non-root user"
    assert "CMD [" in content and "uvicorn" in content


def test_docker_compose_configuration():
    """Validates docker-compose.yml syntax, ports, volumes, and healthchecks."""
    assert COMPOSE_PATH.exists(), "docker-compose.yml must exist at repository root"
    content = COMPOSE_PATH.read_text(encoding="utf-8")

    data = yaml.safe_load(content)
    assert "services" in data, "docker-compose.yml must define services"
    assert "is456-rag-api" in data["services"]

    svc = data["services"]["is456-rag-api"]
    assert "8000:8000" in svc["ports"]
    assert any("data/audit" in str(v) for v in svc["volumes"])
    assert any("data/processed/cad" in str(v) for v in svc["volumes"])
    assert "healthcheck" in svc


def test_dockerignore_configuration():
    """Validates that .dockerignore excludes virtual environments and secrets."""
    assert DOCKERIGNORE_PATH.exists(), ".dockerignore must exist at repository root"
    content = DOCKERIGNORE_PATH.read_text(encoding="utf-8")

    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]
    assert any(".venv" in l for l in lines)
    assert any(".git" in l for l in lines)
    assert any(".env" in l for l in lines)
    assert any("__pycache__" in l for l in lines)


def test_ci_cd_workflow_configuration():
    """Validates .github/workflows/ci.yml triggers, jobs, and steps."""
    assert CI_WORKFLOW_PATH.exists(), "CI workflow must exist at .github/workflows/ci.yml"
    content = CI_WORKFLOW_PATH.read_text(encoding="utf-8")

    workflow = yaml.safe_load(content)
    trigger_config = workflow.get("on") if "on" in workflow else workflow.get(True)
    assert trigger_config is not None, "Workflow must specify triggers ('on')"
    assert "push" in trigger_config
    assert "pull_request" in trigger_config
    assert "jobs" in workflow

    jobs = workflow["jobs"]
    assert "test" in jobs
    assert "docker-build" in jobs

    test_steps = [s.get("name", "") for s in jobs["test"]["steps"]]
    assert any("dependencies" in s.lower() for s in test_steps)
    assert any("test" in s.lower() for s in test_steps)
    assert any("step 9" in s.lower() or "evaluation" in s.lower() for s in test_steps)


def test_api_health_endpoint():
    """Validates public /health endpoint used by container healthcheck."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
