Status: draft pilot. Passes the implemented IS 456 beam detailing checks only. Not engineer-reviewed.

# Maintenance and Operations Guide

## 1. Overview

This document outlines the operational procedures, maintenance routines, test execution steps, and index rebuilding workflows for this codebase.

All commands assume a local Python environment activated from the repository root.

---

## 2. Rebuilding Chunks and Vector Indices

When clause text, headings, cross-references, or table entries in `data/processed/` are modified, the unified chunk dataset and dense embeddings must be rebuilt.

### 2.1 Rebuilding `chunks.jsonl`
The chunk synthesis script compiles individual JSON files into the unified dataset:
```powershell
.venv\Scripts\python -m src.chunking.build_chunks
```
- **Inputs**:
  - `data/processed/is456_cl_26_5_1.json`
  - `data/processed/is456_table_16.json`
  - `data/processed/is456_table_19.json`
  - `data/processed/is456_table_20.json`
  - `data/processed/is456_xu_max_table.json`
  - `data/processed/is456_annex_g.json`
  - `data/processed/is456_cl_40.json`
- **Output**: `data/processed/chunks.jsonl` (contains exactly 23 structured JSON lines).

### 2.2 Rebuilding Dense Embeddings
After updating `chunks.jsonl`, regenerate the dense embeddings array:
```powershell
.venv\Scripts\python -m src.retrieval.dense_search --rebuild
```
- **Model**: `BAAI/bge-small-en-v1.5` (downloads weights locally from HuggingFace cache if not present).
- **Outputs**:
  - `data/processed/embeddings.npy`: Binary NumPy array of dimensions `(23, 384)`.
  - `data/processed/embedding_ids.json`: List of 23 chunk IDs mapping row indices to chunks.

---

## 3. Test Suite Execution

The repository contains automated unit and integration tests under `tests/`.

### 3.1 Running the Full Test Suite
Execute the entire test collection:
```powershell
.venv\Scripts\pytest tests/
```

### 3.2 Key Test Areas Covered
- **API Tests (`test_api.py`)**: Tests `GET /health`, `POST /v1/rag/query`, authentication header validation, and audit log generation.
- **Sizing Engine (`test_beam_sizing.py`)**: Tests flexural sizing, shear calculations, and parameter boundaries across load cases.
- **CAD Export (`test_cad_export.py`)**: Validates entity creation, layers, dimensions, and DXF format compliance.
- **Chunk Schemas (`test_chunks.py`, `test_schema.py`)**: Verifies Pydantic v2 data models and metadata fields.
- **Table Integrity (`test_table_16.py`, `test_table_19.py`, `test_table_20.py`, `test_xu_max_table.py`)**: Checks boundary conditions, row lookups, and numeric values against standard data.
- **Validation Modules (`test_is456_checks.py`, `test_is456_flexure.py`, `test_is456_shear.py`)**: Verifies deterministic math for limiting neutral axis, minimum steel, and shear reinforcement.
- **LLM Client (`test_llm_client.py`)**: Tests mocking, header propagation, and content parsing.
- **Evaluation Benchmark (`test_evaluation.py`)**: Runs design scenario self-consistency checks.

---

## 4. Evaluation and Benchmark Execution

### 4.1 Master Step 9 Evaluation Suite
To execute the unified, four-pillar Step 9 evaluation benchmark:
```powershell
.venv\Scripts\python -m src.evaluation.run_step9_master_eval
```
- **Pillar 1 (RAG Retrieval Quality)**: Evaluates 19 benchmark questions for Hit@1 (84.2%), Hit@3 (100.0%), and MRR (0.9123).
- **Pillar 2 (Hand-Calculation Cross-Checks)**: Cross-checks deterministic engine against 4 hand-calculated examples (written by the author of this repository, not published values).
- **Pillar 3 (Real-World Design Scenarios)**: Tests 5 building loading scenarios with self-consistency, arithmetic re-checks from JSON tables, under-reinforced checks ($x_u/d \le x_{u,\max}/d$), and automated 2D CAD DXF export.
- **Pillar 4 (Faithfulness & Citation Audit)**: Verifies that explanation narratives match deterministic sizing outputs with deterministic numerical consistency, 100% valid IS 456 clause citations, and mandatory structural disclaimers.
- **Output Report**: `data/eval/step9_master_evaluation_report.json`.

### 4.2 Hand-Calculation Cross-Checks
To run the standalone hand-calculation cross-checks:
```powershell
.venv\Scripts\python src/evaluation/run_sp16_eval.py
```
- Tests flexural tension steel $A_{st}$, percentage steel $p_t$, neutral axis ratio $x_u/d$, shear stress $\tau_v, \tau_c$, and required stirrup spacing against reference hand calculations.
- Generates `data/eval/sp16_evaluation_report.json`.

### 4.3 Retrieval Pipeline Evaluation
To evaluate retrieval performance against the 19 questions in `data/eval/questions.json`:
```powershell
.venv\Scripts\python -m src.evaluation.run_rerank_eval
```
- Evaluates Hit@1 and Hit@3 metrics for the cross-encoder reranker (`BAAI/bge-reranker-base`).
- Compares individual ranking positions across BM25, Dense search, Hybrid fusion, and Cross-Encoder reranking.

Individual search stages can also be inspected:
```powershell
.venv\Scripts\python -m src.evaluation.run_dense_eval
.venv\Scripts\python -m src.evaluation.run_hybrid_eval
.venv\Scripts\python -m src.evaluation.run_retrieval_eval
```

### 4.4 Structural Design Evaluation
To evaluate the deterministic sizing engine across design scenarios:
```powershell
.venv\Scripts\python src/evaluation/run_design_eval.py
```
- Evaluates 5 realistic loading scenarios from `data/eval/structural_design_scenarios.json`.
- Runs self-consistency checks where the same code rules design and check the section.
- Runs an arithmetic re-check from the JSON tables directly, using the same design shear force $V_u$ and the same Table 19 row rule as the sizing flow.
- Generates 2D DXF files for each scenario.
- Exports a detailed benchmark report to `data/eval/design_evaluation_report.json`.

---

## 5. Audit Log Maintenance

The API logs search queries to `data/audit/audit.jsonl`.
- **Growth**: The file grows linearly with every query to `POST /v1/rag/query`.
- **Maintenance**: Periodically archive or rotate `audit.jsonl` if disk storage is constrained. The directory structure `data/audit/` is automatically created if absent.

---

## 6. Remote Colab Model Maintenance

When using the LLM detailing proposal feature:
1. Open and run all cells in `colab/ollama_test.ipynb` on Google Colab.
2. Note the newly generated public tunnel URL and authentication token.
3. Update the local environment configuration (`OLLAMA_BASE_URL` and `OLLAMA_API_TOKEN`) accordingly.
4. If the Colab runtime disconnects due to inactivity or resource timeouts, repeat steps 1–3.

---

## 7. Engineering Assumptions

The following parameters and heuristics are not specified on the referenced IS 456 pages and are included in the codebase as assumptions:

1. **Assumption: Load factor**: Service loads are multiplied by a single factor of 1.5 ($w_u = 1.5(DL + LL)$) per Table 18.
2. **Assumption: Default support width**: Effective span is calculated per Cl. 22.2(a) as $\min(\text{clear span} + d, \text{clear span} + \text{support width})$, with support bearing width defaulted to an assumed value of 300 mm when not provided by the user. (Unit weight of reinforced concrete is verified as 25.0 kN/m³ per Cl. 19.2.1).
3. **Assumption: Preliminary depth guess**: Preliminary effective depth trial is assumed as $\text{span} / 14$ rounded up to 25 mm, with overall depth $D = d + \text{cover} + 25\text{ mm}$ rounded up to 25 mm. The actual effective depth $d_{\text{actual}} = D - \text{cover} - \phi_{\text{stirrup}} - \phi_{\text{bar}} / 2$ is subsequently recomputed from the chosen rebar diameters.
4. **Assumption: Stirrup sizes tried**: Stirrup diameters are evaluated strictly in sequence across 8 mm, 10 mm, and 12 mm.
5. **Assumption: Minimum spacing**: A minimum spacing threshold of 100 mm is enforced; smaller spacing triggers `needs_review`.
6. **Assumption: Rounding to 5 mm**: Stirrup spacing is rounded down to the nearest 5 mm multiple for constructability.
7. **Assumption: Table 19 row rule**: For concrete shear strength $\tau_c$, the lookup selects the row where $p_t \le \text{calculated } p_t$ without linear interpolation (using row 1 if $p_t < 0.15$ and the last row if $p_t \ge 3.0$).
8. **Assumption: Deflection modification factor F1**: The tension modification factor $F_1$ is evaluated using an approximate curve fit, not from IS 456 (Fig. 4 has not yet been digitized from the page). Deflection check results are indicative only. Fig. 4 covers $p_t$ from 0 to 3.0 and $f_s$ from 120 to 290 N/mm²: if $p_t > 3.0$ or $f_s > 290\text{ N/mm}^2$, status is set to `needs_review` with the note "Outside the range of Fig. 4"; if $f_s < 120\text{ N/mm}^2$, $f_s = 120\text{ N/mm}^2$ is used and noted. Upper limit on $F_1$ is 2.0 with no lower limit, and no lower bound on $p_t$.
9. **Assumption: 20 mm nominal maximum aggregate size**: Per Cl. 26.3.2(a), horizontal clear distance between main bars must be at least $\max(\phi_{\text{bar}}, \text{aggregate size} + 5\text{ mm})$. A 20 mm nominal maximum aggregate size (giving a 25 mm clearance floor) is assumed unless an alternative value is explicitly provided.

---

## 8. Not implemented

The following maintenance capabilities, automation workflows, member types, and structural components are not implemented in this repository:
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
