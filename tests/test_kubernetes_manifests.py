"""
Static validation of the Step 10 Kubernetes manifests in k8s/.

These tests parse the YAML and assert its structure, security posture, probe
wiring and volume wiring. They do NOT need a cluster, kubectl or Docker, and
they make no claim that the manifests have been applied to a live cluster.

No manifest content or secret value is ever printed.
"""

from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml

K8S_DIR = Path("k8s")
NAMESPACE = "is-rag"
API_APP_LABEL = "is-rag-api"


def _load_documents() -> List[Dict[str, Any]]:
    """Loads every YAML document from k8s/."""
    assert K8S_DIR.is_dir(), "k8s/ directory must exist at the repository root"
    files = sorted(K8S_DIR.glob("*.yaml"))
    assert files, "k8s/ must contain at least one YAML manifest"

    documents: List[Dict[str, Any]] = []
    for path in files:
        with open(path, "r", encoding="utf-8") as handle:
            for doc in yaml.safe_load_all(handle):
                if doc:
                    documents.append(doc)
    return documents


def _by_kind(documents: List[Dict[str, Any]], kind: str) -> List[Dict[str, Any]]:
    return [d for d in documents if d.get("kind") == kind]


def _named(documents: List[Dict[str, Any]], kind: str, name: str) -> Dict[str, Any]:
    for doc in _by_kind(documents, kind):
        if doc.get("metadata", {}).get("name") == name:
            return doc
    raise AssertionError(f"{kind} '{name}' not found in k8s/")


@pytest.fixture(scope="module")
def manifests() -> List[Dict[str, Any]]:
    return _load_documents()


def test_every_document_is_a_valid_kubernetes_object(manifests):
    """Each document declares apiVersion, kind and a named, namespaced metadata block."""
    assert len(manifests) >= 8, "k8s/ should define the full Step 10 object set"
    for doc in manifests:
        assert doc.get("apiVersion"), "manifest missing apiVersion"
        assert doc.get("kind"), "manifest missing kind"
        metadata = doc.get("metadata") or {}
        assert metadata.get("name"), f"{doc.get('kind')} manifest missing metadata.name"
        if doc.get("kind") == "Namespace":
            continue  # the Namespace object itself is cluster-scoped
        assert metadata.get("namespace") == NAMESPACE, (
            f"{doc.get('kind')}/{metadata.get('name')} is not in the '{NAMESPACE}' namespace"
        )


def test_required_object_set_is_present(manifests):
    """The deployment covers namespace, config, secrets, storage, database and API."""
    kinds = {doc.get("kind") for doc in manifests}
    for required in ("Namespace", "ConfigMap", "Secret", "Deployment", "StatefulSet"):
        assert required in kinds, f"k8s/ must define a {required}"

    service_names = {s["metadata"]["name"] for s in _by_kind(manifests, "Service")}
    assert {"is-rag-api", "is-rag-postgres"} <= service_names

    pvc_names = {p["metadata"]["name"] for p in _by_kind(manifests, "PersistentVolumeClaim")}
    assert {"is-rag-audit", "is-rag-cad", "is-rag-vector-store", "is-rag-model-cache"} <= pvc_names


def test_api_deployment_runs_single_close_to_the_embedded_vector_store(manifests):
    """
    The embedded Qdrant client holds an exclusive file lock on a ReadWriteOnce
    volume, so the deployment must be single replica with a Recreate strategy.
    """
    deployment = _named(manifests, "Deployment", API_APP_LABEL)
    spec = deployment["spec"]

    assert spec["replicas"] == 1
    assert spec["strategy"]["type"] == "Recreate"
    assert spec["selector"]["matchLabels"]["app.kubernetes.io/component"] == "api"


def test_api_container_is_hardened(manifests):
    """Non-root, no privilege escalation, dropped capabilities and a read-only root filesystem."""
    pod_spec = _named(manifests, "Deployment", API_APP_LABEL)["spec"]["template"]["spec"]
    pod_security = pod_spec["securityContext"]

    assert pod_security["runAsNonRoot"] is True
    assert pod_security["runAsUser"] == 1000
    assert pod_security["runAsGroup"] == 1000
    assert pod_security["seccompProfile"]["type"] == "RuntimeDefault"

    container = pod_spec["containers"][0]
    container_security = container["securityContext"]
    assert container_security["allowPrivilegeEscalation"] is False
    assert container_security["readOnlyRootFilesystem"] is True
    assert container_security["capabilities"]["drop"] == ["ALL"]


def test_api_container_probes_are_health_endpoint_based(manifests):
    """Startup, readiness and liveness all probe the public /health endpoint."""
    container = _named(manifests, "Deployment", API_APP_LABEL)["spec"]["template"]["spec"]["containers"][0]

    for probe_name in ("startupProbe", "readinessProbe", "livenessProbe"):
        probe = container[probe_name]
        assert probe["httpGet"]["path"] == "/health", f"{probe_name} must probe /health"
        assert probe["httpGet"]["port"] == "http"
        assert probe["periodSeconds"] > 0

    # The first start builds the vector index from the chunk corpus, so the
    # startup budget must be far more generous than the liveness budget.
    assert container["startupProbe"]["failureThreshold"] >= 30
    assert container["startupProbe"]["failureThreshold"] > container["livenessProbe"]["failureThreshold"]


def test_api_container_declares_resources_and_config_sources(manifests):
    """Explicit requests/limits are set and config is injected from the ConfigMap and Secret."""
    container = _named(manifests, "Deployment", API_APP_LABEL)["spec"]["template"]["spec"]["containers"][0]

    assert container["resources"]["requests"]["memory"]
    assert container["resources"]["requests"]["cpu"]
    assert container["resources"]["limits"]["memory"]
    assert container["imagePullPolicy"] in ("IfNotPresent", "Always", "Never")

    env_from = container["envFrom"]
    assert {"configMapRef": {"name": "is-rag-config"}} in env_from
    assert {"secretRef": {"name": "is-rag-secrets"}} in env_from


def test_api_writable_paths_are_backed_by_declared_volumes(manifests):
    """Audit logs, DXF output, the vector store and the model cache are all persisted."""
    pod_spec = _named(manifests, "Deployment", API_APP_LABEL)["spec"]["template"]["spec"]
    container = pod_spec["containers"][0]

    claim_by_mount_path = {}
    volumes_by_name = {v["name"]: v for v in pod_spec["volumes"]}
    for mount in container["volumeMounts"]:
        volume = volumes_by_name.get(mount["name"])
        assert volume is not None, f"volumeMount '{mount['name']}' has no matching volume"
        if "persistentVolumeClaim" in volume:
            claim_by_mount_path[mount["mountPath"]] = volume["persistentVolumeClaim"]["claimName"]

    assert claim_by_mount_path["/app/data/audit"] == "is-rag-audit"
    assert claim_by_mount_path["/app/data/processed/cad"] == "is-rag-cad"
    assert claim_by_mount_path["/app/data/processed/qdrant_storage"] == "is-rag-vector-store"
    assert claim_by_mount_path["/app/.cache/huggingface"] == "is-rag-model-cache"

    # The image root filesystem is read-only, so a scratch volume must be mounted.
    assert any(v.get("emptyDir") is not None for v in pod_spec["volumes"])

    declared_claims = {p["metadata"]["name"] for p in _by_kind(manifests, "PersistentVolumeClaim")}
    assert set(claim_by_mount_path.values()) <= declared_claims
    for claim in declared_claims:
        assert "ReadWriteOnce" in _named(manifests, "PersistentVolumeClaim", claim)["spec"]["accessModes"]


def test_api_service_selects_the_api_pods(manifests):
    """The ClusterIP Service port 80 maps onto the container's named http port."""
    service = _named(manifests, "Service", "is-rag-api")
    deployment_labels = _named(manifests, "Deployment", API_APP_LABEL)["spec"]["selector"]["matchLabels"]

    assert service["spec"]["type"] == "ClusterIP"
    assert service["spec"]["selector"] == deployment_labels

    port = service["spec"]["ports"][0]
    assert port["port"] == 80
    assert port["targetPort"] == "http"

    container = _named(manifests, "Deployment", API_APP_LABEL)["spec"]["template"]["spec"]["containers"][0]
    assert any(p["name"] == "http" and p["containerPort"] == 8000 for p in container["ports"])


def test_config_map_supplies_non_secret_runtime_settings(manifests):
    """Database location, cache location and the optional LLM URL come from the ConfigMap."""
    data = _named(manifests, "ConfigMap", "is-rag-config")["data"]

    assert data["POSTGRES_HOST"] == "is-rag-postgres"
    assert data["POSTGRES_DB"] == "is_codes_db"
    assert data["HF_HOME"].startswith("/app/")
    assert "IS_RAG_API_KEYS" not in data, "API keys must never live in a ConfigMap"
    assert "POSTGRES_PASSWORD" not in data, "Passwords must never live in a ConfigMap"


def test_secret_contains_only_placeholders(manifests):
    """No real credential may be committed; every secret value must be a placeholder or empty."""
    secret = _named(manifests, "Secret", "is-rag-secrets")
    values = secret.get("stringData") or {}

    assert set(values) == {"IS_RAG_API_KEYS", "POSTGRES_USER", "POSTGRES_PASSWORD", "OLLAMA_API_TOKEN"}
    assert "REPLACE_ME" in values["IS_RAG_API_KEYS"]
    assert values["POSTGRES_PASSWORD"].startswith("REPLACE_ME")
    assert values["OLLAMA_API_TOKEN"] == ""


def test_postgres_statefulset_is_reachable_and_persistent(manifests):
    """The StatefulSet points at its headless Service and claims its own volume."""
    statefulset = _named(manifests, "StatefulSet", "is-rag-postgres")
    service = _named(manifests, "Service", "is-rag-postgres")

    assert service["spec"]["clusterIP"] == "None"
    assert statefulset["spec"]["serviceName"] == service["metadata"]["name"]

    claims = statefulset["spec"]["volumeClaimTemplates"]
    assert claims, "PostgreSQL data must live on a volumeClaimTemplate"
    assert claims[0]["metadata"]["name"] == "postgres-data"

    container = statefulset["spec"]["template"]["spec"]["containers"][0]
    assert container["volumeMounts"][0]["name"] == "postgres-data"
    assert container["readinessProbe"]["exec"]["command"]

    env_by_name = {e["name"]: e for e in container["env"]}
    assert env_by_name["POSTGRES_PASSWORD"]["valueFrom"]["secretKeyRef"]["key"] == "POSTGRES_PASSWORD"
    assert env_by_name["POSTGRES_PASSWORD"]["valueFrom"]["secretKeyRef"]["name"] == "is-rag-secrets"


def test_api_deployment_pulls_the_image_published_by_ci(manifests):
    """The container image is the registry path and tag produced by the CI docker-build job."""
    container = _named(manifests, "Deployment", API_APP_LABEL)["spec"]["template"]["spec"]["containers"][0]

    assert container["image"].startswith("ghcr.io/"), (
        "the Deployment must reference a registry-qualified image, not a bare local tag"
    )
    assert container["image"].endswith(":latest")


def test_api_and_postgres_agree_on_the_database_host_and_name(manifests):
    """The API connects to the Service name that actually fronts PostgreSQL."""
    config = _named(manifests, "ConfigMap", "is-rag-config")["data"]
    postgres_service = _named(manifests, "Service", "is-rag-postgres")
    postgres_db_env = _named(manifests, "StatefulSet", "is-rag-postgres")["spec"]["template"]["spec"]["containers"][0]["env"]

    assert config["POSTGRES_HOST"] == postgres_service["metadata"]["name"]
    assert config["POSTGRES_PORT"] == str(postgres_service["spec"]["ports"][0]["port"])

    db_env = next(e for e in postgres_db_env if e["name"] == "POSTGRES_DB")
    assert db_env["valueFrom"]["configMapKeyRef"]["key"] == "POSTGRES_DB"
