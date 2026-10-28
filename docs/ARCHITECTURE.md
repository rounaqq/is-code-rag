Status: draft pilot. Passes the implemented IS 456 beam detailing checks only. Not engineer-reviewed.

# System Architecture

## 1. Overview and Design Objectives

This repository implements a modular structural engineering assistant and information retrieval system over several Indian Standards: **IS 456:2000** (Plain and Reinforced Concrete), **IS 800:2007** (General Construction in Steel), **IS 875** (Design Loads), **IS 1893 (Part 1):2016** (Earthquake Resistant Design) and **IS 13920:2016** (Ductile Detailing), supported by the SP:16, SP:34 and SP:24 handbooks. IS 456:2000 is digitized to clause and table level; the remaining codes are indexed at clause level.

The codebase separates deterministic structural mechanics from semantic information retrieval and generative language modeling:
1. **Deterministic Sizing and Validation Engine**: Computes bending moments, shear forces, longitudinal steel areas, stirrup spacing, column axial capacity, slab moments and footing bearing/punching checks using deterministic formulas directly mapped from digitized standard tables and clauses.
2. **Hybrid Retrieval and Reranking Pipeline**: Serves queries from a Qdrant collection of 996 chunks spanning all 5 indexed codes, using lexical BM25, dense semantic vectors (`BAAI/bge-small-en-v1.5`), Reciprocal Rank Fusion (RRF), and cross-encoder reranking (`BAAI/bge-reranker-base`). A separate IS 456:2000 path indexes the 23 digitized clause and table chunks directly from `chunks.jsonl`.
3. **Seismic Design Checks**: Computes IS 1893 (Part 1) base shear ($V_B = A_h W$) and resolves conflicts where IS 13920 ductile provisions supersede IS 456 in seismic Zones III–V.
4. **2D CAD Drafting**: Automatically draws cross-sections, longitudinal elevations and plan views of designed beams, columns, slabs and isolated footings in DXF format using `ezdxf`.
5. **LLM Front-End and Proposal Modules**: Connect to an external Ollama instance to extract structured parameters from natural-language requests and to propose reinforcement detailing from retrieved clause text; the deterministic Python engine retains authority over every number.
6. **Review and Evaluation Gates**: Signed engineer-review records control the DRAFT/Reviewed status of exported drawings, and the Step 9 evaluation pillars provide retrieval, grounding and hand-calculation cross-check evidence.

```mermaid
flowchart TD
    subgraph Data Layer
        P0["data/raw/*.pdf\n(10 acquired standards & handbooks)"]
        P1["data/processed/is456_*.json\n(Clauses 26.5.1, 40, Annex G, Tables 16, 19, 20, xu_max)"]
        P2["data/processed/chunks.jsonl\n(23 structured IS 456 chunks)"]
        P3["data/processed/embeddings.npy\n(384-dim dense vectors)"]
        P4["data/processed/qdrant_storage\n(Qdrant: 996 chunks, 5 codes)"]
        P0 --> P1
        P1 --> P2
        P2 --> P3
        P2 --> P4
    end

    subgraph Retrieval Pipeline
        Q["User Query"] --> BM25["BM25 Search\n(rank-bm25)"]
        Q --> Dense["Dense Search\n(Qdrant + bge-small-en-v1.5)"]
        P4 --> Dense
        P3 --> Dense
        BM25 --> RRF["Reciprocal Rank Fusion\n(RRF k=60)"]
        Dense --> RRF
        RRF --> Reranker["Cross-Encoder Reranker\n(bge-reranker-base)"]
        Reranker --> Results["Top-k Chunks\nwith Rerank Score"]
    end

    subgraph Deterministic Sizing Engine
        Inputs["Span, Loads, fck, fy,\nExposure, Seismic Zone"] --> Sizing["beam_sizing.py / column_sizing.py\nslab_sizing.py / footing_sizing.py"]
        P1 -->|Direct JSON Table Access| Sizing
        Sizing --> Shear["is456_shear.py\n(Shear Design & Table 19 Lookup)"]
        P1 -->|Direct JSON Table Access| Shear
        Sizing --> Seismic["seismic_base_shear.py\n(IS 1893 Base Shear)"]
        Seismic --> Compliance["seismic_compliance.py\n(IS 13920 vs IS 456 resolution)"]
        Shear --> Validation["design_validation.py / is456_checks.py\n(Self-Consistency Checks)"]
        Compliance --> Validation
        Validation --> CAD["beam / column / slab / footing _dxf.py\n(2D DXF Generation)"]
        CAD --> Review["engineer_review.py\n(DRAFT / Reviewed stamping)"]
    end

    subgraph LLM Detailing
        Results --> LLM_Prompt["LLM Prompt Builder"]
        LLM_Prompt --> LLM_Client["llm_client.py\n(Remote Ollama / Tunnel)"]
        LLM_Client --> LLM_Out["Extracted Detailing JSON"]
        LLM_Out --> Sizing
    end
```

---

## 2. Core Subsystems

### 2.1 Retrieval Engine (`src/retrieval/`)
The retrieval pipeline delivers relevant clauses and tables for user queries without hallucinating clause text. Two stores back it: the embedded Qdrant collection (`qdrant_db.py`, 996 chunks across all 5 indexed codes) and the IS 456 `embeddings.npy` / `chunks.jsonl` pair (23 chunks).
- **Lexical Search (`bm25_search.py`)**: Uses `rank-bm25` over tokenized text from `chunks.jsonl`.
- **Embedded Vector Store (`qdrant_db.py`)**: Disk-backed Qdrant local client holding the multi-standard collection `structural_is_codes` (BGE-small, 384-dim, cosine). Chunks are consolidated from `chunks.jsonl` and the per-code preprocessed JSON, and payload filtering is applied on the `code` attribute. The collection is created automatically on first use.
- **Dense Vector Search (`dense_search.py`)**: Generates 384-dimensional dense vectors using HuggingFace's `BAAI/bge-small-en-v1.5` sentence transformer model, saved in `data/processed/embeddings.npy`. Similarity is computed via normalized dot product (cosine similarity).
- **Reciprocal Rank Fusion (`hybrid_search.py`)**: Merges BM25 and dense ranking results with a smoothing parameter $k = 60$:
  $$RRF\_Score(d) = \frac{1}{60 + rank_{BM25}(d)} + \frac{1}{60 + rank_{Dense}(d)}$$
- **Multi-Standard Search (`multicode_search.py`)**: Runs BM25 and Qdrant dense search over the full multi-code corpus and fuses them with RRF; this is the path the API serves for normal queries.
- **Cross-Encoder Reranking (`rerank.py`)**: Passes candidate query-chunk pairs into `BAAI/bge-reranker-base` to generate a relevance logit score.
- **Pipeline Facade (`pipeline.py`)**: Exposes `retrieve(query, k=3)`. Loads chunk metadata once into memory and returns top-$k$ verified text chunks.

### 2.2 Sizing and Mechanics Engine (`src/generation/`, `src/validation/`)
The deterministic sizing code computes cross-section dimensions and reinforcement detailing for each member type:
- **Direct Table Reading**: Sizing functions read directly from `data/processed/is456_table_19.json`, `is456_table_20.json`, and `is456_xu_max_table.json`. The sizing functions themselves take plain numeric inputs; callers such as the design assistant (see 2.3) supply parameters that were extracted from retrieved clauses, so retrieval does feed the sizing flow.
- **Beam Sizing (`beam_sizing.py`)**: Evaluates neutral axis limiting ratio $x_{u,\max}/d$ from Table under Cl. 38.1 and limiting moment capacity $M_{u,\lim} = 0.36 (x_{u,\max}/d)(1 - 0.42 x_{u,\max}/d) b d^2 f_{ck}$ per Annex G-1.1(c). Evaluates required tension steel $A_{st}$ using the quadratic formula from Annex G-1.1(b).
- **Column Sizing (`column_sizing.py`)**: Computes short-column axial capacity, longitudinal steel percentage limits per Cl. 26.5.3.1, lateral tie spacing and diameter per Cl. 26.5.3.2, and a minimum-eccentricity moment per Cl. 25.4 with biaxial interaction checking.
- **Slab Sizing (`slab_sizing.py`)**: Computes one-way and two-way slab moments, minimum and required reinforcement, and checks overall depth against the span/depth rules of Cl. 23.2 with Table 16 clear cover.
- **Footing Sizing (`footing_sizing.py`)**: Sizes isolated footings for bearing pressure, one-way shear, punching shear per Cl. 34, and computes the required reinforcement distribution.
- **Shear Design (`src/validation/is456_shear.py`)**: Computes nominal shear stress $\tau_v = V_u / (b d)$ per Cl. 40.1. Looks up concrete design shear strength $\tau_c$ from Table 19 and verifies $\tau_v \le \tau_{c,\max}$ from Table 20. If $\tau_v > \tau_c$, computes shear carried by stirrups $V_{us} = V_u - \tau_c b d$ and required stirrup spacing per Cl. 40.4(a). If $\tau_v \le \tau_c$, applies minimum shear reinforcement spacing per Cl. 26.5.1.6.
- **Seismic Checks (`src/validation/seismic_base_shear.py`, `seismic_compliance.py`)**: Computes the IS 1893 (Part 1) base shear $V_B = A_h W$ from the design horizontal acceleration coefficient and seismic weight, and applies IS 13920:2016 ductile-detailing provisions (confinement, dimensional and reinforcement rules) where they supersede IS 456 in Zones III–V.

### 2.3 LLM Client and Front-End Assistant (`src/generation/`)
- **LLM Tool-Calling Front-End (`design_assistant.py`)**: Connects the LLM as the conversational front-end for structural engineers. The LLM parses the engineer's natural language request, extracts structured parameters (`span_m`, `dead_load_kN_per_m`, `live_load_kN_per_m`, `fck`, `fy`, `exposure`, `b`, `support_width_mm`), calls the deterministic sizing tool `size_beam_from_loads`, and explains the results with verified IS 456:2000 clause citations (Cl. 19.2.1, Cl. 22.2(a), Cl. 36.4.1/Table 18, Cl. 38.1 & Annex G, Cl. 40, Cl. 23.2.1 [F1: approximate curve fit, not from IS 456], Cl. 26.2.1 & 26.2.3.3). The deterministic Python code in `beam_sizing.py` stays in charge of every number. A consistency guardrail (`verify_explanation_consistency`) checks that narrative values match calculation outputs, and the mandatory structural review disclaimer is strictly enforced.
- **LLM Client (`llm_client.py`)**: Interacts with an Ollama HTTP server via `/api/chat`. Accepts `OLLAMA_BASE_URL` and sends the authentication token in the `X-LLM-Token` header. Reads responses strictly from `message.content` (ignoring internal model reasoning traces).
- **Proposal Flow (`design_proposal.py`)**: Retrieval-backed proposal flow that pulls clauses through `src/retrieval/pipeline.py`, formulates a prompt containing the retrieved text, and queries the LLM for bar detailing. Detailing parameters are validated through `src/validation/is456_checks.py`.

### 2.4 2D CAD Drafting (`src/cad/`)
- Employs `ezdxf` to produce AutoCAD-compatible DXF files (version R2010) for each member type: `beam_dxf.py`, `column_dxf.py`, `slab_dxf.py`, and `footing_dxf.py`.
- **Beam (`beam_dxf.py`)** builds two viewports:
  1. **Cross-Section (Section A-A)**: Shows beam width $b$, overall depth $D$, clear cover, closed stirrup outer loop, bottom tension bars, and top hanger bars.
  2. **Longitudinal Elevation**: Shows clear span, support bearing blocks, top and bottom reinforcement bars, distributed vertical shear stirrups, and anchorage hooks. Development length $L_d$ is evaluated per Cl. 26.2.1 and 26.2.1.1, with minimum support anchorage embedment ($L_d / 3$) per Cl. 26.2.3.3.
- **Column (`column_dxf.py`)** draws the column cross-section (boundary, longitudinal bars, outer tie with hooks, dimensions) and a longitudinal elevation with main bars and horizontal ties at the design pitch.
- **Slab (`slab_dxf.py`)** draws a cross-section elevation through the span (slab thickness, supports, cover per Table 16, main and distribution reinforcement).
- **Footing (`footing_dxf.py`)** draws a plan view (footing boundary, column outline, bottom reinforcement mesh, dimension strings) and an elevation cross-section.
- Organized across dedicated CAD layers (`OUTLINE`, `REBAR_MAIN`, `REBAR_TOP`, `STIRRUPS`, `DIMENSIONS`, `ANNOTATIONS`, `TITLE_BLOCK`, `HATCH`).
- Every exported drawing is stamped **`STATUS: DRAFT - NOT FOR CONSTRUCTION. Not engineer-reviewed.`** until a signed review record exists. `engineer_review.py` holds the sign-off path (`sign_off_design()` / `export_approved_dxf()`) that controls the DRAFT/Reviewed title-block status.

### 2.5 API Service (`src/api/main.py`)
- Built on FastAPI, exposing 14 endpoints:
  - **Health**: `GET /health`
  - **Retrieval**: `POST /v1/rag/query` (IS 456 path), `POST /v1/rag/multicode/query` (multi-standard hybrid search)
  - **Design assistant**: `POST /v1/design/assistant`
  - **Beam**: `POST /v1/design/review`, `POST /v1/design/dxf`
  - **Column**: `POST /v1/design/column/review`, `POST /v1/design/column/dxf`
  - **Slab**: `POST /v1/design/slab/review`, `POST /v1/design/slab/dxf`
  - **Footing**: `POST /v1/design/footing/review`, `POST /v1/design/footing/dxf`
  - **Seismic**: `POST /v1/validation/seismic-compliance`, `POST /v1/design/seismic/base-shear`
- Validates the `X-API-Key` header against `IS_RAG_API_KEYS`.
- Preloads retrieval models during startup lifespan.
- Records query details, returned chunk IDs, rerank scores, latency, and client key name to an append-only JSONL log at `data/audit/audit.jsonl`.

---

## 3. Engineering Assumptions

The following design decisions and parameters are not specified on the referenced IS 456:2000 pages and are implemented as engineering assumptions:

1. **Assumption: Load factor**: A single partial safety factor of 1.5 is multiplied against combined service dead and live loads ($w_u = 1.5(DL + LL)$) to calculate design moment $M_u$ and design shear force $V_u$. Other load combinations from Table 18 are not considered.
2. **Assumption: Default support width**: Effective span is calculated per Cl. 22.2(a) as $\min(\text{clear span} + d, \text{clear span} + \text{support width})$, with support bearing width defaulted to an assumed value of 300 mm when not provided by the user. (Unit weight of reinforced concrete is verified as 25.0 kN/m³ per Cl. 19.2.1).
3. **Assumption: Preliminary depth guess**: Preliminary trial effective depth uses $\text{span} / 14$ rounded up to the nearest 25 mm multiple (minimum 200 mm floor). The actual effective depth $d_{\text{actual}} = D - \text{cover} - \phi_{\text{stirrup}} - \phi_{\text{bar}} / 2$ is subsequently computed from the chosen bar geometry, aligning sizing calculations and CAD drawing.
4. **Assumption: Stirrup sizes tried**: Stirrup bar diameters are evaluated in a fixed trial sequence of 8 mm, then 10 mm, then 12 mm, choosing the first size yielding a calculated spacing of at least 100 mm.
5. **Assumption: Minimum spacing**: A practical fabrication floor of 100 mm is assumed for stirrup spacing. If the required spacing is below 100 mm, the design is flagged as `needs_review`.
6. **Assumption: Rounding to 5 mm**: Calculated stirrup spacing is rounded down to the nearest multiple of 5 mm (`math.floor(spacing / 5.0) * 5.0`) for construction detailing; spacing is never rounded up.
7. **Assumption: Table 19 row rule**: For concrete shear strength $\tau_c$, the lookup selects the table row where $p_t \le \text{calculated } p_t$ without linear interpolation (if $p_t < 0.15$ the first row is selected; if $p_t \ge 3.0$ the last row is selected).
8. **Assumption: Deflection modification factor F1**: The tension modification factor $F_1$ is evaluated using an approximate curve fit, not from IS 456 (Fig. 4 has not yet been digitized from the page). Deflection check results are indicative only. Fig. 4 covers $p_t$ from 0 to 3.0 and $f_s$ from 120 to 290 N/mm²: if $p_t > 3.0$ or $f_s > 290\text{ N/mm}^2$, status is set to `needs_review` with the note "Outside the range of Fig. 4"; if $f_s < 120\text{ N/mm}^2$, $f_s = 120\text{ N/mm}^2$ is used and noted. Upper limit on $F_1$ is 2.0 with no lower limit, and no lower bound on $p_t$.
9. **Assumption: 20 mm nominal maximum aggregate size**: Per Cl. 26.3.2(a), horizontal clear distance between main bars must be at least $\max(\phi_{\text{bar}}, \text{aggregate size} + 5\text{ mm})$. A 20 mm nominal maximum aggregate size (giving a 25 mm clearance floor) is assumed unless an alternative value is explicitly provided.

---

## 4. Not implemented

The following capabilities, member types, and infrastructure components are not implemented in this repository:
- DWG (drawings are exported as DXF only)
- amendment tracking (no amendment or revision records for standards or designs)
- incremental updates (the corpus and vector index are rebuilt, not incrementally refreshed)
- doubly reinforced and T-beams (singly reinforced rectangular beams only)
- multi-turn interactive conversational memory (each query is answered independently)
- live Kubernetes cluster verification (the manifests in `k8s/` are provided and statically validated, but have not been applied to a running cluster)
