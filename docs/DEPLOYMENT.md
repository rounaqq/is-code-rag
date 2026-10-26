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
- Build context is filtered via `.dockerignore` to prevent leaking local virtual environments (`.venv`), secrets (`.env`), or cache files.

---

## 3. Continuous Integration and Delivery (CI/CD)

The repository includes an automated GitHub Actions pipeline defined in [`.github/workflows/ci.yml`](file:///.github/workflows/ci.yml):
- **Triggers**: Executed automatically on every `push` or `pull_request` targeting `master` or `main`.
- **Workflow Jobs**:
  1. **`test`**:
     - Sets up Python 3.12 on Ubuntu Linux.
     - Caches pip dependencies.
     - Verifies chunk synthesis and vector indices integrity (`python -m src.chunking.build_chunks`).
     - Executes the full 134-test regression suite (`pytest tests/ -v`).
     - Executes the Step 9 master evaluation suite (`python -m src.evaluation.run_step9_master_eval`).
     - Archives evaluation and benchmark reports as build artifacts for 14 days.
  2. **`docker-build`**:
     - Runs upon successful completion of the test job.
     - Validates that the Docker container builds cleanly without missing packages or layer errors.

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

The following infrastructure, member types, standards, and automation features are not implemented in this repository:
- other IS codes
- columns
- slabs
- footings
- DWG
- amendment tracking
- incremental updates
- doubly reinforced and T-beams
- the LLM not connected to the sizing flow
- retrieval not used by the sizing code
