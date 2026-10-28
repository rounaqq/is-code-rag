# Structural IS Code RAG Pipeline for AI-Driven 2D CAD Design
## Complete 10-Step Implementation Architecture & Compliance Report

> **Pipeline Version**: 2.0 (Multi-Standard Structural Engineering RAG)  
> **Covered Codes**: IS 456:2000, IS 13920:2016, IS 875 (Parts 1–3), IS 1893 (Part 1):2016, IS 800:2007  
> **Handbooks & Design Aids**: SP:16 (Design Aids to IS 456), SP:34 (Detailing Handbook), SP:24 (Explanatory Handbook)  
> **Target 2D CAD Outputs**: RC Beams, RC Columns, RC Slabs, RC Footings, Steel Connections (DXF R2010 via `ezdxf`)  
> **Compliance & Safety**: Clause-level citations, deterministic Python calculation checks, mandatory draft watermarking.

---

## 1. Executive Summary & Step-by-Step Mapping

| Manager's 10-Step Requirement | Status | Implementation Files | Key Capabilities & Outputs |
| :--- | :---: | :--- | :--- |
| **Step 1: Requirement Analysis & Scope Definition** | **COMPLETED** | `docs/REQUIREMENT_ANALYSIS_AND_SCOPE.md` | Defined scope for 5 Indian Standards, layer standards, CAD lineweights, compliance rules, zero-hallucination math constraint. |
| **Step 2: Data Acquisition & Collection** | **COMPLETED** | `src/ingestion/download_codes.py`<br>`data/raw/registry.json`<br>`data/raw/DVC_MANIFEST.md`<br>`.gitattributes` | Automated acquisition pipeline with SHA-256 validation. Acquired official PDFs for IS 456, IS 13920, IS 875 (Parts 1, 2, 3), IS 1893 (Part 1), IS 800, SP:16, SP:34, SP:24. Versioned with Git LFS & DVC. |
| **Step 3: Document Preprocessing & OCR** | **COMPLETED** | `src/ingestion/ocr_preprocessor.py`<br>`src/ingestion/figure_equation_extractor.py`<br>`data/tessdata/eng.traineddata` | Solved BIS proprietary font encoding corruption using PyMuPDF C-engine OCR (200 DPI). Extracted 129 figures and 1,955 equations across all 10 documents (1,226 pages, 270 OCR fallback pages), each cropped to PNG, caption-linked to its "FIG. n" label, and indexed in `figures_equations.json`. |
| **Step 4: Chunking & Metadata Enrichment** | **COMPLETED** | `data/processed/is13920_preprocessed.json`<br>`data/processed/is875_part_2_preprocessed.json`<br>`data/processed/is1893_part_1_preprocessed.json`<br>`data/processed/is800_preprocessed.json` | Clause-level chunking preserving hierarchy (e.g. `6.4.2`, `7.6.1`). Metadata tags for applicability, structural dependencies, keywords, and formula indicators. |
| **Step 5: Vector Indexing & Hybrid Retrieval** | **COMPLETED** | `src/retrieval/qdrant_db.py`<br>`src/retrieval/multicode_search.py`<br>`data/processed/qdrant_storage` | Embedded Qdrant vector database (v1.20) indexing 996 chunks across all 5 standards with BGE-small embeddings (384-dim, cosine), BM25Okapi, Reciprocal Rank Fusion (RRF k=60), and native metadata payload filtering. |
| **Step 6: Compliance Reasoning Engine & Conflict Resolution** | **COMPLETED** | `src/validation/seismic_compliance.py`<br>`src/generation/seismic_base_shear.py` | Automatically resolves conflicts where IS 13920 ductile provisions supersede IS 456 in seismic zones III–V. Deterministic base shear $V_B = A_h W$ calculator per IS 1893. |
| **Step 7: 2D CAD Generation & Parameter Mapping** | **COMPLETED** | `src/cad/beam_dxf.py`<br>`src/cad/column_dxf.py`<br>`src/cad/slab_dxf.py`<br>`src/cad/footing_dxf.py` | Headless DXF generation using `ezdxf`. Produces longitudinal sections, cross-sections, stirrup zones, bar callouts, 135° seismic hooks, and title blocks. |
| **Step 8: Quality Assurance & Safety Guardrails** | **COMPLETED** | `src/generation/design_validation.py`<br>`src/cad/engineer_review.py` | Design Rule Checking (DRC) for shear ceiling, deflection, bar clearance, minimum/maximum steel percentages. Immutable draft watermark on all blueprints. |
| **Step 9: API & Integration Layer** | **COMPLETED** | `src/api/main.py` | REST API with API key authentication and audit logging. Endpoints for multi-code search, seismic compliance checking, base shear calculation, and DXF exports. |
| **Step 10: Testing, Validation & Deployment** | **COMPLETED** | `tests/` (34 modules)<br>`Dockerfile`<br>`docker-compose.yml`<br>`k8s/`<br>`.github/workflows/ci.yml` | 248 automated test functions (252 collected cases) verifying data acquisition, OCR extraction, Qdrant search, multi-code RRF search, seismic compliance, API security, and the Kubernetes manifests. Ships the Docker image, Compose service and the `k8s/` manifest set; CI runs the regression suite and the Step 9 master evaluation. |

---

## 2. Step 3: Document Preprocessing & OCR Deep Dive

### The Corrupt Font Encoding Challenge
Official Bureau of Indian Standards (BIS) electronic PDFs (specifically `IS 13920:2016` and `IS 1893:2016`) were published using proprietary font encodings without standard `/ToUnicode` CMap tables. Standard text extractors (`pypdf`, `pdfplumber`, naive `page.get_text()`) extract corrupted glyphs like `'\x01\x02 \x03\x04\x05'` or `F %%!`.

### Solution Architecture
1. **Dynamic Heuristic Corruption Detector**: Checks alphanumeric character ratio against total non-whitespace characters. If readable English character ratio $< 65\%$, flags page as corrupted/scanned.
2. **In-Memory Tesseract OCR Engine**: PyMuPDF embeds the Tesseract OCR C-library directly. By provisioning `data/tessdata/eng.traineddata`, PyMuPDF renders pages at 200 DPI in memory and extracts 100% legible English text and tables without external binary dependencies.
3. **Extraction Statistics**:
   - `IS 13920:2016`: 33 pages (24 OCR), 125 structured clauses extracted.
   - `IS 875 (Part 2):1987`: 23 pages, 94 structured clauses extracted.
   - `IS 1893 (Part 1):2016`: 56 pages (40 OCR), 229 structured clauses extracted.
   - `IS 800:2007`: 158 pages, 1,012 structured clauses extracted.

### Figure & Equation Extraction
Text alone does not carry the engineering intent of an IS code, so `src/ingestion/figure_equation_extractor.py` pulls the non-textual content out of every acquired PDF:

- **Figure detection**: `page.get_image_info(xrefs=True)` locates embedded and inline raster images. Full-page scan backgrounds (area ≥ 85% of the page) and decorative glyphs (below 60 × 40 pt / 3,000 pt²) are filtered out; each remaining region is rendered to PNG at 150 DPI.
- **Caption linking**: `page.get_text("blocks")` is scanned for `FIG. n` / `Fig. n` / `Figure n` labels within 45 pt below a figure region with horizontal overlap, so every figure carries its official label and caption.
- **Equation detection**: `page.get_text("dict")` provides line-level boxes. A line is treated as an equation when it is a standalone numbered reference (e.g. `(1)`, `(2a)`) or a formula line carrying an `=` with operands on both sides and at least one digit (unit strings such as `N/mm2` are rejected). Formula regions are cropped to PNG with their text preserved, so no LLM ever has to re-type a formula.
- **OCR-aware**: pages flagged by the corruption heuristic (`is_text_corrupt_or_empty`) are re-read through the same in-memory Tesseract engine at 200 DPI before caption/equation extraction, so IS 13920, IS 1893 and the SP handbooks yield legible results despite their proprietary font encodings.
- **Unified index & merge**: results are written to `data/processed/figures_equations.json` and merged into the Step-4 `*_preprocessed.json` files, adding per-page `figure_ids` / `equation_ids` and per-document figure/equation references.

| Document | Pages | OCR Pages | Figures | Equations |
| :--- | :---: | :---: | :---: | :---: |
| IS 456:2000 | 114 | 4 | 32 | 147 |
| IS 13920:2016 | 33 | 24 | 20 | 32 |
| IS 875 (Part 1):1987 | 43 | 1 | 6 | 119 |
| IS 875 (Part 2):1987 | 23 | 1 | 12 | 33 |
| IS 875 (Part 3):2015 | 69 | 1 | 16 | 221 |
| IS 1893 (Part 1):2016 | 56 | 44 | 15 | 70 |
| IS 800:2007 | 158 | 1 | 10 | 570 |
| SP:16:1980 | 255 | 146 | 6 | 445 |
| SP:34:1987 | 289 | 38 | 6 | 169 |
| SP:24:1983 | 186 | 10 | 6 | 149 |
| **Total** | **1,226** | **270** | **129** | **1,955** |

---

## 3. Step 5: Qdrant Vector Database & Hybrid Retrieval Engine

### Vector Database Architecture
- **Engine**: Qdrant Local Client (`qdrant-client` v1.20) running 100% offline via embedded disk storage at `data/processed/qdrant_storage`. Zero external SaaS dependencies or API keys.
- **Embedding Model**: `BAAI/bge-small-en-v1.5` (384-dimensional dense semantic vectors with cosine similarity metric).
- **Index Size**: 996 structural chunks indexing all 5 Indian Standards:
  - IS 456:2000 (Plain & Reinforced Concrete)
  - IS 13920:2016 (Ductile Detailing of RC Structures under Seismic Forces)
  - IS 1893 (Part 1):2016 (Criteria for Earthquake Resistant Design of Structures)
  - IS 875 (Part 2):1987 (Design Imposed / Live Loads)
  - IS 800:2007 (General Construction In Steel)
- **Hybrid Retrieval Fusion**:
  $$\text{RRF\_Score}(d) = \sum_{m \in \{\text{BM25}, \text{Qdrant}\}} \frac{1.0}{k + \text{rank}_m(d)}$$
  where $k = 60$. Combines exact lexical engineering tokens (clause decimals like `6.3.3`, `Table 16`, steel grades) with dense semantic generalization.
- **Metadata Payload Filtering**:
  Native Qdrant `Filter` with `FieldCondition` on `code` enabling instant standard-isolated queries (`code_filter='IS 13920'`) or cross-code federated retrieval.

---

## 4. Step 6: Seismic Conflict Resolution Matrix (IS 456 vs IS 13920)

In Seismic Zones III, IV, and V, the ductile detailing provisions of **IS 13920:2016** supersede the general provisions of **IS 456:2000**:

```
┌─────────────────────────────────┬──────────────────────┬────────────────────────┬─────────────────────────────────────────┐
│ Parameter                       │ IS 456:2000 Limit    │ IS 13920:2016 Limit    │ Governing Precedence & Engineering Rationale │
├─────────────────────────────────┼──────────────────────┼────────────────────────┼─────────────────────────────────────────┤
│ Beam Minimum Width              │ 150–200 mm           │ b >= 200 mm; b/D >= 0.3│ IS 13920 Cl. 6.1.1 GOVERNS. Prevents    │
│                                 │ (no strict floor)    │                        │ lateral-torsional buckling under cyclic.│
├─────────────────────────────────┼──────────────────────┼────────────────────────┼─────────────────────────────────────────┤
│ Maximum Tension Steel (pt,max)  │ pt <= 4.0%           │ pt <= 2.5%             │ IS 13920 Cl. 6.2.2 GOVERNS. Prevents    │
│                                 │ (Cl. 26.5.1.1b)      │ (Cl. 6.2.2)            │ brittle over-reinforced concrete crush. │
├─────────────────────────────────┼──────────────────────┼────────────────────────┼─────────────────────────────────────────┤
│ Minimum Tension Steel (pt,min)  │ pt >= 0.85 / fy      │ pt >= 0.24*sqrt(fck)/fy│ IS 13920 Cl. 6.2.1 GOVERNS. Higher      │
│                                 │ (~0.20% for Fe415)   │ (~0.29% for M25/Fe415) │ steel ensures distributed micro-cracks. │
├─────────────────────────────────┼──────────────────────┼────────────────────────┼─────────────────────────────────────────┤
│ Stirrup Spacing at Supports     │ <= min(0.75d, 300 mm)│ Over length 2d:        │ IS 13920 Cl. 6.3.3 GOVERNS. Provides    │
│ (Plastic Hinge Zone)            │ (Cl. 26.5.1.5)       │ <= min(d/4, 8*db, 100) │ concrete core confinement in hinges.    │
├─────────────────────────────────┼──────────────────────┼────────────────────────┼─────────────────────────────────────────┤
│ Transverse Tie Hooks            │ 90° hook with 8*db   │ 135° hook with >=10*db │ IS 13920 Cl. 5.2 GOVERNS. Prevents tie  │
│                                 │ extension            │ (min 65 mm extension)  │ unzipping after concrete cover spalls.  │
├─────────────────────────────────┼──────────────────────┼────────────────────────┼─────────────────────────────────────────┤
│ Column Special Confinement (lo) │ Standard tie pitch   │ Over lo = max(D, H/6,  │ IS 13920 Cl. 7.6.1 GOVERNS. Prevents    │
│                                 │ <= min(b, 16*db, 300)│ 450 mm): pitch <= 100mm│ explosive shear failure at column ends. │
└─────────────────────────────────┴──────────────────────┴────────────────────────┴─────────────────────────────────────────┘
```

---

## 5. Deterministic Seismic Base Shear ($V_B$) per IS 1893:2016

The base shear calculation strictly follows:
$$V_B = A_h \cdot W$$
Where:
$$A_h = \frac{Z}{2} \cdot \frac{I}{R} \cdot \left(\frac{S_a}{g}\right)$$
- **Zone Factor $Z$ (Table 2)**: Zone II = 0.10, Zone III = 0.16, Zone IV = 0.24, Zone V = 0.36.
- **Importance Factor $I$ (Table 6)**: Hospital/School = 1.5, Dense Commercial = 1.2, Residential = 1.0.
- **Response Reduction $R$ (Table 7)**: SMRF (Ductile) = 5.0, OMRF = 3.0, Steel CBF = 4.0.
- **Fundamental Natural Period $T_a$ (Cl. 7.6.2)**:
  - Bare RC Frame: $T_a = 0.075 \cdot h^{0.75}$
  - Bare Steel Frame: $T_a = 0.085 \cdot h^{0.75}$
  - Infill Frame: $T_a = \frac{0.09 \cdot h}{\sqrt{d}}$
- **Storey Drift Serviceability Limit (Cl. 7.11.1)**: $\Delta \le 0.004 \cdot h_i$.

---

## 6. API Endpoint Reference

| HTTP Method & Path | Description | Authentication |
| :--- | :--- | :---: |
| `GET /health` | Liveness health check | Public (no key required) |
| `POST /v1/rag/query` | Authenticated IS 456 clause/table retrieval with cross-encoder reranking and audit logging | Header: `X-API-Key` |
| `POST /v1/design/assistant` | IS 456 design assistant: deterministic sizing plus clause-cited explanation | Header: `X-API-Key` |
| `POST /v1/design/review` | Step 8 engineer review & feedback loop for beams (review sheet, overrides, formal record) | Header: `X-API-Key` |
| `POST /v1/design/dxf` | Generates 2D CAD beam longitudinal elevation & cross-section DXF | Header: `X-API-Key` |
| `POST /v1/design/column/review` | IS 456 RC column design & sizing (short axial, minimum eccentricity, ties) | Header: `X-API-Key` |
| `POST /v1/design/column/dxf` | Generates 2D CAD column cross-section, elevation, ties, and 135° hooks DXF | Header: `X-API-Key` |
| `POST /v1/design/slab/review` | IS 456 RC slab design & sizing (thickness, deflection, flexural steel) | Header: `X-API-Key` |
| `POST /v1/design/slab/dxf` | Generates 2D CAD one-way/two-way floor slab cross-section & plan DXF | Header: `X-API-Key` |
| `POST /v1/design/footing/review` | IS 456 RC isolated footing design & sizing (plan, punching shear, mesh) | Header: `X-API-Key` |
| `POST /v1/design/footing/dxf` | Generates 2D CAD isolated footing plan & cross-section DXF | Header: `X-API-Key` |
| `POST /v1/rag/multicode/query` | Federated multi-code search across IS 456, IS 13920, IS 875, IS 1893, IS 800 | Header: `X-API-Key` |
| `POST /v1/validation/seismic-compliance` | Automated conflict resolution and compliance checks between IS 456 and IS 13920 | Header: `X-API-Key` |
| `POST /v1/design/seismic/base-shear` | Deterministic IS 1893 base shear, $A_h$, $T_a$, and drift check calculator | Header: `X-API-Key` |

---

## 7. Master Evaluation Framework & RAGAS-style Offline Proxy Metrics

`src/evaluation/run_step9_master_eval.py` consolidates the quality gates into a single
report at `data/eval/step9_master_evaluation_report.json`.

| Pillar | What it checks | Source of truth | Gates the master pass? |
| :--- | :--- | :--- | :---: |
| **1 - Retrieval quality** | Hit@1 / Hit@3 / MRR over the 19 labelled questions | Labelled `expected_chunk_id` | Yes |
| **2 - Hand-calculation cross-checks** | Engine vs. author-written hand calculations | Written by the author of this repository (not published values) | Yes |
| **3 - Design scenarios & CAD** | 5 building scenarios, self-consistency, arithmetic re-checks, DXF export | Deterministic sizing engine | Yes |
| **4 - Faithfulness & citations** | Numerical sourcing, disclaimer presence, citation validity | Deterministic sizing engine | Yes |
| **5 - RAGAS-style proxy metrics** | Retrieval precision@k / recall@k / MRR + faithfulness / relevancy proxies | Labelled questions (retrieval) and rule-based claim grounding (proxies) | Recall@k only |
| **6 - Independent engineer review** | Blind package + attestation record | A genuine, independent reviewer | **Never** |

### 7.1 RAGAS-style offline proxy metrics (rule-based - not the RAGAS library)

`src/evaluation/rag_metrics.py` implements rule-based **proxies** for three RAGAS metric
definitions - faithfulness, answer relevancy and context relevancy - and
`src/evaluation/run_rag_metrics_eval.py` writes `data/eval/rag_metrics_report.json`.

These are **proxies**, computed offline and deterministically; the `ragas`/`trulens`
packages are **not installed or imported** and no network access is used. The report is
labelled "RAGAS-style offline proxy metrics" and states explicitly that it is not the
RAGAS library. Relevancy is a secondary proxy derived from the project's existing
`BAAI/bge-small-en-v1.5` embeddings.

Grounding rules (rule-based claim extraction: clause references, identifiers, numbers):

- **Clause answers** - every number, identifier and clause reference must appear in the retrieved chunks.
- **Design explanations** - every number must match the calculator output (plus explicitly declared standard constants) and every cited clause must appear in the retrieved chunk set. **Calculated numbers are not required to appear in chunks**, because the calculator - not the retriever - is their source of truth.

The report carries:

- **Retrieval metrics** - precision@k, recall@k and MRR computed from the labelled questions, reported **per code** and for the **multi-code set**.
- **Faithfulness** - reported **separately** for templated (code-written) answers and model-written answers. The templated figure is **partly circular** (the same deterministic code that produced the numbers also grounds them); the model-written figure is only produced when an LLM endpoint is reachable, otherwise it is reported `UNAVAILABLE` - nothing is fabricated.
- **IS-compliance accuracy** - recorded as **`PENDING`** (no value), because it needs a source independent of this repository (a published worked example or a licensed engineer's verdict).

Only the label-based retrieval recall@k gates Pillar 5; the faithfulness and relevancy
proxies are reported for information.

### 7.2 Independent engineer review (never auto-approves)

`src/evaluation/run_independent_review.py` builds a **blind review package**
(`data/eval/independent_review_package.json`) containing the design inputs and computed
designs, the governing assumption list and the unsourced items - but **not** the author's
expected answers (`expected_checks` / `governing_clauses` are deliberately omitted so the
reviewer is not anchored).

The module defines and validates `data/eval/independent_review_record.json` with fields
`author_name`, `reviewer_name`, `role`, `registration_number`, `date`, `scope`, and a
per-design list of `{scenario_id, outcome, comments}`. A record is **rejected** when the
reviewer equals the author or when required attestation fields are missing.

Hard honesty rules:

- Scripts and tests **never create a record and never invent a reviewer**; the module only reads and validates one.
- Pillar 6 reads **"PENDING - not evaluated"** until a valid record exists, and it is **never counted as a pass**.
- Drawings stay **"DRAFT - NOT FOR CONSTRUCTION. Not engineer-reviewed."** until a valid record is loaded; when one is loaded the title block reads **"Reviewed by <name>, <date>: <outcome>"** and **never "approved"**.

### 7.3 Evaluation artifacts

| Artifact | Produced by | Contents |
| :--- | :--- | :--- |
| `data/eval/step9_master_evaluation_report.json` | `run_step9_master_eval.py` | Consolidated pillars 1-6 |
| `data/eval/rag_metrics_report.json` | `run_rag_metrics_eval.py` | RAGAS-style proxy metrics |
| `data/eval/independent_review_package.json` | `run_independent_review.py` | Blind review package |
| `data/eval/independent_review_record.json` | **A genuine independent reviewer (never generated here)** | Attestation record |

---

## 8. Step 10: Deployment & Maintenance Infrastructure

### 8.1 Deployment surfaces

| Surface | Artifacts | Notes |
| :--- | :--- | :--- |
| Local container | `Dockerfile`, `docker-compose.yml`, `.dockerignore` | `python:3.12-slim` base, non-root `appuser` (UID 1000), `curl`-based `HEALTHCHECK` on `/health`, audit and CAD volumes. The git-ignored vector index is excluded from the build context. |
| Orchestrated | `k8s/00-namespace.yaml` … `k8s/06-api-service.yaml` | Namespace `is-rag`, ConfigMap `is-rag-config`, Secret `is-rag-secrets` (placeholders only), PostgreSQL StatefulSet with a headless Service, four PVCs, API Deployment and ClusterIP Service. |
| CI/CD | `.github/workflows/ci.yml` | `test` job (optional DVC corpus restore, chunk synthesis, full `pytest` suite, Step 9 master evaluation, report artifacts) followed by `docker-build`, which publishes `ghcr.io/<owner>/<repo>:sha-<short>` and `:latest` on the default branch. |

### 8.2 Kubernetes design constraints

- **Single replica with `strategy: Recreate`.** The embedded Qdrant local client holds an exclusive file lock on `data/processed/qdrant_storage`, and every claim is `ReadWriteOnce`. A second replica cannot start against the same volume, and a rolling update would stall on a volume the old pod still holds. Horizontal scale-out requires Qdrant server mode or a read-only index baked into the image.
- **Read-only root filesystem.** Only the write paths are overlaid: PVCs for `data/audit`, `data/processed/cad`, `data/processed/qdrant_storage` and the HuggingFace cache, plus an `emptyDir` at `/tmp`. The read-only corpus baked into the image at `/app/data` stays visible.
- **First start builds the index.** `data/processed/qdrant_storage` is git-ignored, so the first pod downloads `BAAI/bge-small-en-v1.5` and embeds the 996-chunk corpus into its PVC. The startup probe allows 10 minutes (`60 × 10 s`); liveness stays at 3 failures.
- **Probes ride on the lifespan warm-up.** Uvicorn serves only after the FastAPI startup hook loads the embedding and reranker models, so a passing `/health` probe proves the retrieval stack is live.
- **No credential is committed.** `is-rag-secrets` holds `REPLACE_ME` placeholders; API keys and the database password are deliberately absent from the ConfigMap, and the manifest test fails if a non-placeholder value is committed.

### 8.3 Verification status

- **Kubernetes**: statically validated by `tests/test_kubernetes_manifests.py` (12 tests covering object set, namespacing, security context, probe wiring, volume wiring and placeholder-only secrets). The manifests have **not been applied to a live cluster** — no cluster runtime is available on the development workstation — so no Kubernetes runtime behaviour is claimed.
- **Docker/Compose**: manifest definitions validated by `tests/test_deployment.py`; the actual image build is exercised only by the CI `docker-build` job.
- **Maintenance is manual.** Amendment tracking, incremental re-indexing and embedding retraining are not automated; the rebuild and refresh procedures are documented in `docs/MAINTENANCE.md`.

