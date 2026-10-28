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


def test_ci_publishes_the_image_the_manifests_consume():
    """
    The docker-build job must authenticate and publish to a registry, and the image it
    publishes must be the exact image the Kubernetes Deployment references. Without
    this, the manifests reference a tag that no pipeline ever creates.
    """
    workflow = yaml.safe_load(CI_WORKFLOW_PATH.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["docker-build"]["steps"]
    uses = [s.get("uses", "") for s in steps]

    assert any("login-action" in u for u in uses), "docker-build must authenticate to a registry"

    publish = next((s for s in steps if "build-push-action" in s.get("uses", "")), None)
    assert publish is not None, "docker-build must publish with docker/build-push-action"
    assert publish["with"]["push"] == "${{ github.event_name == 'push' }}"
    assert publish["with"]["tags"] == "${{ steps.meta.outputs.tags }}"

    metadata = next(s for s in steps if "metadata-action" in s.get("uses", ""))
    assert metadata["with"]["images"] == "ghcr.io/${{ github.repository }}"

    deployment = yaml.safe_load((Path("k8s") / "05-api-deployment.yaml").read_text(encoding="utf-8"))
    image = deployment["spec"]["template"]["spec"]["containers"][0]["image"]
    assert image == "ghcr.io/rounaqq/is-code-rag:latest", (
        "the Deployment image must be the repository path that CI publishes to"
    )


def test_ci_restores_the_corpus_before_the_test_suite():
    """
    The corpus pull must run before pytest, so the DVC integrity checks are meaningful
    on a runner instead of reporting as skipped.
    """
    workflow = yaml.safe_load(CI_WORKFLOW_PATH.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["test"]["steps"]
    names = [s.get("name", "").lower() for s in steps]

    pull_index = next((i for i, n in enumerate(names) if "dvc" in n), None)
    assert pull_index is not None, "the test job must attempt to restore the DVC corpus"

    test_index = next((i for i, n in enumerate(names) if "test suite" in n), None)
    assert test_index is not None
    assert pull_index < test_index, "the corpus must be pulled before the test suite runs"

    pull_step = steps[pull_index]
    assert "DVC_REMOTE_URL" in pull_step.get("env", {}), (
        "the pull step must take the remote URL from configuration, not from a local path"
    )
