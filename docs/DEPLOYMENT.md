Status: draft pilot. Passes the implemented IS 456 beam detailing checks only. Not engineer-reviewed.

# Deployment and Infrastructure Guide

## 1. Overview

This document describes how the services, retrieval pipelines, external language model tunnels, container environments, and CI/CD automation in this repository are executed and deployed.

The system supports both local virtual environment execution and reproducible containerized deployment via Docker and Docker Compose, with continuous integration automated via GitHub Actions.

---

## 2. Containerized Deployment (Docker & Docker Compose)

### 2.1 Building and Running via Docker Compose
To run the containerized service locally:
```powershell
docker compose up --build -d
```
- **Service Name**: `is456-rag-api`
- **Exposed Port**: `8000` (mapped to `http://localhost:8000`)
- **Healthcheck**: Automated HTTP health check probing `GET /health` every 30 seconds.
- **Volumes**:
  - `./data/audit:/app/data/audit`: Persists query audit logs.
  - `./data/processed/cad:/app/data/processed/cad`: Persists generated DXF CAD files.

### 2.2 Standalone Docker Container
To build and run directly with the Docker CLI:
```powershell
# Build image
docker build -t is456-rag-api:latest .

# Run container
docker run -d \
  --name is456-rag \
  -p 8000:8000 \
  -e IS_RAG_API_KEYS="test_engineer:FAKE_DEMO_KEY_FOR_LOCAL_TESTING_ONLY,prod_client:FAKE_PROD_KEY_FOR_LOCAL_TESTING_ONLY" \
  -v ${PWD}/data/audit:/app/data/audit \
  -v ${PWD}/data/processed/cad:/app/data/processed/cad \
  is456-rag-api:latest
```

### 2.3 Container Security & Non-Root Execution
- The image runs under a dedicated unprivileged user (`appuser`, UID 1000).
- Root access is restricted inside the runtime container.
- Build context is filtered via `.dockerignore` to prevent leaking local virtual environments (`.venv`), secrets (`.env`), or cache files. The locally built vector index (`data/processed/qdrant_storage/`) is excluded as well, so the image never ships machine-specific Qdrant state.

### 2.4 Kubernetes Manifests (`k8s/`)

All objects live in the `is-rag` namespace and are applied with a single command:

```powershell
kubectl apply -f k8s/
kubectl -n is-rag get pods,svc,pvc
```

| File | Objects |
| :--- | :--- |
| `k8s/00-namespace.yaml` | Namespace `is-rag` |
| `k8s/01-configmap.yaml` | ConfigMap `is-rag-config` (non-secret runtime settings) |
| `k8s/02-secret.yaml` | Secret `is-rag-secrets` (placeholders only) |
| `k8s/03-postgres.yaml` | Headless Service + StatefulSet `is-rag-postgres` with a `volumeClaimTemplate` |
| `k8s/04-api-volumes.yaml` | PVCs `is-rag-audit`, `is-rag-cad`, `is-rag-vector-store`, `is-rag-model-cache` |
| `k8s/05-api-deployment.yaml` | Deployment `is-rag-api` |
| `k8s/06-api-service.yaml` | ClusterIP Service `is-rag-api` (port 80 to container port 8000) |

Design decisions that are specific to this application:

1. **Single replica with `strategy: Recreate`.** The embedded Qdrant local client takes an exclusive file lock on its storage path, and the claims are `ReadWriteOnce`. A second replica would fail to start, and a rolling update would wait forever on a volume the previous pod still holds. Horizontal scale-out would require running Qdrant as a server or baking a read-only index into the image.
2. **Only the writable paths are overlaid.** The image keeps its read-only data at `/app/data` (chunk corpus, JSON tables, DXF fixtures); the Deployment mounts PVCs over `data/audit`, `data/processed/cad`, `data/processed/qdrant_storage` and the HuggingFace cache, plus an `emptyDir` at `/tmp` because the container root filesystem is read-only.
3. **First start builds the vector index.** `data/processed/qdrant_storage` is git-ignored and excluded from the image, so the first pod start downloads `BAAI/bge-small-en-v1.5` and indexes the chunk corpus into the `is-rag-vector-store` claim. The startup probe therefore allows up to 10 minutes (`failureThreshold: 60` at 10 s), while liveness stays at 3 failures.
4. **Probes use the public `/health` endpoint.** Uvicorn only starts serving after the FastAPI lifespan warm-up completes, so a successful probe already proves the retrieval models are loaded.
5. **No real credential is committed.** `k8s/02-secret.yaml` holds `REPLACE_ME` placeholders. Create the real Secret with `kubectl -n is-rag create secret generic is-rag-secrets --from-literal=...` before applying, and `tests/test_kubernetes_manifests.py` fails if a non-placeholder value is committed. API keys and passwords are intentionally absent from the ConfigMap.
6. **PostgreSQL is off the request critical path.** It mirrors the chunks for JSONB querying; the API degrades gracefully when the connection is unavailable, which is why the StatefulSet is a plain single replica with a 5 Gi claim.

**Verification status**: the manifests are validated statically by `tests/test_kubernetes_manifests.py` (structure, security context, probes, volume wiring, placeholder-only secrets). **They have not been applied to a live cluster** — no cluster or Docker runtime is available on the development workstation — so no runtime behaviour in Kubernetes is claimed here.

---

## 3. Continuous Integration and Delivery (CI/CD)

The repository includes an automated GitHub Actions pipeline defined in [`.github/workflows/ci.yml`](file:///.github/workflows/ci.yml):
- **Triggers**: Executed automatically on every `push` or `pull_request` targeting `master` or `main`.
- **Workflow Jobs**:
  1. **`test`**:
     - Sets up Python 3.12 on Ubuntu Linux.
     - Caches pip dependencies.
     - Restores the DVC-tracked corpus (`dvc pull`) when the `DVC_REMOTE_URL` repository variable is configured.
     - Verifies chunk synthesis and vector indices integrity (`python -m src.chunking.build_chunks`).
     - Executes the full regression suite (`pytest tests/ -v`), which includes the static Kubernetes manifest validation in `tests/test_kubernetes_manifests.py` and the corpus SHA-256 check in `tests/test_data_acquisition.py`.
     - Executes the Step 9 master evaluation suite (`python -m src.evaluation.run_step9_master_eval`).
     - Archives evaluation and benchmark reports as build artifacts for 14 days.
  2. **`docker-build`**:
     - Runs upon successful completion of the test job, with `packages: write` permission.
     - Builds, tags and **publishes** the image to GitHub Container Registry as `ghcr.io/<owner>/<repo>:sha-<short>`, plus `:latest` on the default branch.
     - Pull requests only build the image (`push: false`), so fork builds cannot publish.

### 3.1 Repository configuration required for a complete CI run

| Name | Kind | Purpose |
| :--- | :--- | :--- |
| `DVC_REMOTE_URL` | Repository **variable** (`vars`) | Shared DVC remote holding the 10 PDFs, e.g. `s3://<bucket>/is-code-rag`. The committed remote is a local directory (`data/dvc_remote`), which does not exist on a runner. |
| `DVC_AWS_ACCESS_KEY_ID`, `DVC_AWS_SECRET_ACCESS_KEY` | Repository **secrets** | Credentials for an S3-compatible remote, exported as `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`. Other backends need their own environment variables. |

Two behaviours follow from this configuration:

- **With `DVC_REMOTE_URL` set**, the job configures it as a local remote (`dvc remote add -d ci ... --local`, so the committed `.dvc/config` is untouched), pulls the corpus, and the integrity tests verify every file against the SHA-256 digests in `registry.json`. A partial or mismatched restore fails the build.
- **Without it**, the pull step is skipped with a workflow notice, and the corpus checks report as **skipped with a reason** (`raw corpus not present in this checkout`). They never report as passed, so an unverified corpus cannot be mistaken for a verified one.

> **Python version note**: CI and the container both run Python 3.12, while the development virtual environment is Python 3.14. They are not interchangeable until the Linux wheels for `torch`/`sentence-transformers` are validated on 3.14, so a dependency that works locally can still fail the pipeline.

---

## 4. Local Service Execution (Without Docker)

### 4.1 Runtime Environment
- **Operating System**: Windows (tested with PowerShell).
- **Python Version**: Python 3.14 (executed inside local virtual environment `.venv`).
- **Dependencies**: Installed from `requirements.txt`.

### 4.2 FastAPI Server (`src/api/main.py`)
```powershell
.venv\Scripts\uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

#### Endpoints:
1. `GET /health`:
   - Public health check probe (no API key required).
   - Returns `{"status": "ok"}`.
2. `POST /v1/rag/query`:
   - Authenticated structural query endpoint (`X-API-Key` required).
   - Retrieves top-$k$ relevant clauses/tables with cross-encoder reranking.
3. `POST /v1/design/assistant`:
   - Natural language or parameter-based structural design assistant with clause citations.
4. `POST /v1/design/review`:
   - Step 8 engineer review sheet, overrides validation, and formal sign-off.
5. `POST /v1/design/dxf`:
   - Generates and exports downloadable 2D AutoCAD `.dxf` drawing.

#### Audit Logging:
- All queries handled by API endpoints are appended to `data/audit/audit.jsonl`.
- Log records include timestamp, authorized client key name, query text, returned chunk IDs, latency in milliseconds, and HTTP status code. Secret API key strings are never written to disk.

---

## 5. Remote LLM Model and Tunnel Infrastructure

The LLM detailing proposal module (`src/generation/design_proposal.py` and `src/generation/llm_client.py`) interacts with an external Ollama instance rather than running a heavy generative model locally.

### 5.1 Google Colab Setup (`colab/ollama_test.ipynb`)
The model runs on Google Colab using a cloud GPU (e.g., NVIDIA T4):
1. **Installation**: The notebook installs Ollama via `curl -fsSL https://ollama.com/install.sh | sh`.
2. **Server Launch**: Ollama is launched in the background (`ollama serve`), logging to `ollama.log`.
3. **Model Weights**: The designated model (e.g., `gpt-oss:20b`) is downloaded into the Colab environment using `ollama pull`.

### 5.2 Public Tunnel and Authentication
Because Google Colab operates behind NAT without a fixed public IP address:
- A tunneling utility (such as Cloudflare Tunnel, ngrok, or localtunnel) is executed within the Colab environment to forward external HTTPS requests to Ollama's local port (`11434`).
- The local application connects to the tunnel by setting the environment variable `OLLAMA_BASE_URL` to the public tunnel URL.
- Requests pass the authentication token via the `X-LLM-Token` HTTP header (`OLLAMA_API_TOKEN`).

---

## 6. Engineering Assumptions

The following design parameters and heuristics are not specified on the referenced IS 456 pages and are included in the runtime sizing flow as assumptions:

1. **Assumption: Load factor**: Applied service dead and live loads are multiplied by a default factor of 1.5 ($w_u = 1.5(DL + LL)$) per Table 18.
2. **Assumption: Default support width**: Effective span is calculated per Cl. 22.2(a) as $\min(\text{clear span} + d, \text{clear span} + \text{support width})$, with support bearing width defaulted to an assumed value of 300 mm when not provided by the user. (Unit weight of reinforced concrete is verified as 25.0 kN/m³ per Cl. 19.2.1).
3. **Assumption: Preliminary depth guess**: Preliminary effective depth trial is assumed as $\text{span} / 14$ rounded up to 25 mm, with overall depth $D = d + \text{cover} + 25\text{ mm}$ rounded up to 25 mm. The actual effective depth $d_{\text{actual}} = D - \text{cover} - \phi_{\text{stirrup}} - \phi_{\text{bar}} / 2$ is subsequently recomputed from the chosen rebar diameters.
4. **Assumption: Stirrup sizes tried**: Stirrup diameters are evaluated strictly in sequence across 8 mm, 10 mm, and 12 mm.
5. **Assumption: Minimum spacing**: A minimum spacing threshold of 100 mm is enforced; smaller spacing triggers `needs_review`.
6. **Assumption: Rounding to 5 mm**: Stirrup spacing is rounded down to the nearest 5 mm multiple for constructability.
7. **Assumption: Table 19 row rule**: For concrete shear strength $\tau_c$, the lookup selects the row where $p_t \le \text{calculated } p_t$ without linear interpolation (using row 1 if $p_t < 0.15$ and the last row if $p_t \ge 3.0$).
8. **Assumption: Deflection modification factor F1**: The tension modification factor $F_1$ is evaluated using an approximate curve fit, not from IS 456 (Fig. 4 has not yet been digitized from the page). Deflection check results are indicative only. Fig. 4 covers $p_t$ from 0 to 3.0 and $f_s$ from 120 to 290 N/mm²: if $p_t > 3.0$ or $f_s > 290\text{ N/mm}^2$, status is set to `needs_review` with the note "Outside the range of Fig. 4"; if $f_s < 120\text{ N/mm}^2$, $f_s = 120\text{ N/mm}^2$ is used and noted. Upper limit on $F_1$ is 2.0 with no lower limit, and no lower bound on $p_t$.
9. **Assumption: 20 mm nominal maximum aggregate size**: Per Cl. 26.3.2(a), horizontal clear distance between main bars must be at least $\max(\phi_{\text{bar}}, \text{aggregate size} + 5\text{ mm})$. A 20 mm nominal maximum aggregate size (giving a 25 mm clearance floor) is assumed unless an alternative value is explicitly provided.

---

## 7. Not implemented

The following infrastructure, member types, and automation features are not implemented in this repository:
- DWG (drawings are exported as DXF only)
- amendment tracking (no amendment or revision records for standards or designs)
- incremental updates (the corpus and vector index are rebuilt, not incrementally refreshed)
- doubly reinforced and T-beams (singly reinforced rectangular beams only)
- live Kubernetes cluster verification (the manifests in `k8s/` are provided and statically validated, but have not been applied to a running cluster)
