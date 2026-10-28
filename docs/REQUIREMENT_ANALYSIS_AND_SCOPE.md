# Step 1: Requirement Analysis & Scope Definition

> **Document Version**: 2.0 (Multi-Code Structural Pipeline)  
> **Target Standards**: IS 456:2000, IS 13920:2016, IS 875 (Parts 1–3), IS 1893 (Part 1):2016, IS 800:2007  
> **Supplementary Handbooks**: SP:16 (Design Aids), SP:34 (Detailing Handbook), SP:24 (Explanatory Handbook)

---

## 1. Structural IS Code Scope & Applicability Matrix

| Code Identifier | Standard Title & Edition | Primary Engineering Role | Target Structural Members | Key Clauses & Tables |
| :--- | :--- | :--- | :--- | :--- |
| **IS 456:2000** | *Plain and Reinforced Concrete - Code of Practice* (Fourth Revision, Reaffirmed 2021) | Base concrete mechanics, limit state flexure, shear, compression, deflection, durability | Beams, Columns, Solid Slabs, Isolated Footings | Cl. 23.2, Cl. 24, Cl. 26.5, Cl. 34, Cl. 39, Cl. 40, Annex G, Tables 16, 19, 20 |
| **IS 13920:2016** | *Ductile Design and Detailing of Reinforced Concrete Structures Subjected to Seismic Forces* (First Revision) | Seismic ductility, energy dissipation, confinement under cyclic reversal | Beam hinges, Column potential plastic zones, Beam-Column Joint cores | Cl. 6 (Beams), Cl. 7 (Columns & Confining Ties), Cl. 8 (Joints), Cl. 9 (Special Shear Walls) |
| **IS 875 (Part 1):1987** | *Code of Practice for Design Loads: Dead Loads* (Second Revision, Reaffirmed 2018) | Unit weights of structural & architectural building materials | All members (Masonry, Concrete, Finishes, Cladding) | Cl. 2 (Unit weights: RCC = 25 kN/m³, Masonry = 19 kN/m³) |
| **IS 875 (Part 2):1987** | *Code of Practice for Design Loads: Imposed / Live Loads* (Second Revision, Reaffirmed 2018) | Occupancy-based live loads for floors, roofs, stairs, and balconies | Floor slabs, Roofs, Balconies, Corridor beams | Table 1 (Residential = 2.0 kN/m², Office = 2.5–3.0 kN/m², School = 3.0 kN/m², Balcony = 3.0 kN/m²) |
| **IS 875 (Part 3):2015** | *Code of Practice for Design Loads: Wind Loads* (Third Revision) | Basic wind speed map, risk coefficient $k_1$, terrain factor $k_2$, topography $k_3$, wind pressure $p_z$ | Tall frames, Industrial sheds, Roof trusses | Cl. 6.3 (Wind pressure $p_z = 0.6 V_z^2$), Fig. 1 (Wind map of India: 33 to 55 m/s) |
| **IS 1893 (Part 1):2016** | *Criteria for Earthquake Resistant Design of Structures: General Provisions & Buildings* (Sixth Revision) | Seismic hazard zoning, fundamental period $T_a$, spectral acceleration $S_a/g$, base shear $V_B$ | Complete lateral force-resisting frame | Cl. 6.4 (Zone factor $Z$: II=0.10 to V=0.36), Cl. 7.2 (Base shear $V_B = A_h W$) |
| **IS 800:2007** | *General Construction in Steel - Code of Practice* (Third Revision, Reaffirmed 2017) | Structural steel design, Limit state of strength and serviceability | Steel columns, I-beams, Roof trusses, Bolted/Welded connections | Section 6 (Tension), Section 7 (Compression), Section 8 (Flexure), Section 10 (Connections) |

---

## 2. Target 2D CAD Outputs (Blueprints)

All CAD blueprints are exported in industry-standard AutoCAD DXF vector format (`ezdxf`), organized into dedicated layer standards:

```
┌────────────────────────────────────────────────────────────────────────┐
│                       2D CAD TARGET BLUEPRINTS                         │
├─────────────────────┬──────────────────────────────────────────────────┤
│ 1. RC Beams         │ Longitudinal elevation (full span + supports)   │
│                     │ Midspan cross-section A-A (tension rebar)        │
│                     │ Support cross-section B-B (shear stirrups)       │
│                     │ Stirrup distribution spacing zones               │
├─────────────────────┼──────────────────────────────────────────────────┤
│ 2. RC Columns       │ Cross-section plan (dimensions b x D)            │
│                     │ Longitudinal elevation (vertical rebar)          │
│                     │ Lateral confinement ties with 135° seismic hooks │
├─────────────────────┼──────────────────────────────────────────────────┤
│ 3. RC Floor Slabs   │ Plan view (Lx x Ly panel, span direction arrows) │
│                     │ Cross-sectional elevation through span           │
│                     │ Bottom main rebar & transverse distribution mesh │
├─────────────────────┼──────────────────────────────────────────────────┤
│ 4. RC Footings      │ Plan view (base dimensions B x L, column stub)   │
│                     │ Elevation cross-section (depth D, pedestal)      │
│                     │ Column starter dowels bent 90° into bottom mesh  │
├─────────────────────┼──────────────────────────────────────────────────┤
│ 5. Structural Steel │ Truss elevation & connection details             │
│ (Phase 2 Expanded)  │ Gusset plate bolted/welded joint geometry        │
└─────────────────────┴──────────────────────────────────────────────────┘
```

### Layer Standards & Lineweights
- `CONCRETE_OUTLINE`: Continuous, White/Black, Lineweight 0.35 mm
- `REBAR_MAIN`: Continuous, Red, Lineweight 0.50 mm
- `REBAR_STIRRUP` / `REBAR_DIST`: Continuous, Blue/Green, Lineweight 0.35 mm
- `DIMENSIONS`: Continuous, Cyan, Lineweight 0.18 mm
- `TEXT_ANNOTATIONS`: Continuous, Yellow, Lineweight 0.25 mm
- `TITLE_BLOCK`: Continuous, Magenta, Lineweight 0.35 mm
- `WATERMARK`: Continuous, Red, Lineweight 0.70 mm (`STATUS: DRAFT - NOT FOR CONSTRUCTION`)

---

## 3. Compliance & Governance Requirements

1. **Clause-Level Citations**: Every design parameter output MUST cite the exact clause, table, or annex from the relevant standard (e.g., `"IS 456:2000 Cl. 26.5.1.1(a)"`, `"IS 13920:2016 Cl. 7.6.1"`).
2. **Zero-Hallucination Math**: All engineering mathematics are computed deterministically in pure Python. AI/LLMs are strictly restricted to natural language summarization and query understanding; **no formulas or numerical reinforcement values may be invented by an LLM**.
3. **Multi-Rule Code Validator**: Design proposals must pass codified self-consistency checks before CAD generation:
   - Minimum & maximum tension steel percentage
   - Maximum compression steel percentage
   - Shear stress ceiling ($\tau_v \le \tau_{c,max}$)
   - Stirrup & tie spacing limits
   - Slenderness and minimum eccentricity limits
   - Punching shear capacity
   - Span-to-depth deflection criteria
4. **Mandatory Draft Stamp**: All CAD exports must carry an immutable watermark block:
   `STATUS: DRAFT - NOT FOR CONSTRUCTION. Not engineer-reviewed.`

---

## 4. Technology Stack Specification

| Component | Selected Technology | Technical Rationale & Alternatives Evaluated |
| :--- | :--- | :--- |
| **PDF Extraction / Preprocessing** | `PyMuPDF` (`fitz`) | Direct digital text layer extraction preserves decimal points, superscripts, and negative signs without OCR corruption. |
| **OCR Fallback** | `Tesseract OCR` / `pdf2image` | Used only for scanned non-digital paper archives where vector text is absent. |
| **Embeddings** | `BAAI/bge-small-en-v1.5` | SOTA lightweight 384-dimensional dense semantic embedding model with fast CPU inference. |
| **Lexical Search** | `BM25Okapi` | Custom engineering tokenizer preserving hyphenated standard names (`IS-456`, `Cl. 26.5.1.1`). |
| **Hybrid Fusion** | Reciprocal Rank Fusion (RRF $k=60$) | Mathematically balances exact keyword matching with dense semantic similarity. |
| **Reranker** | `BAAI/bge-reranker-base` | Cross-encoder analyzing question and candidate passage jointly, achieving 100% Hit@3 recall. |
| **LLM (Summarization only)** | Ollama, self-hosted on a Google Colab tunnel | Generative model used strictly for natural-language summarization and query understanding (§3.2); no formula or reinforcement value is ever produced by the LLM. Authenticated with an `X-LLM-Token` header; base URL, model and token are supplied via environment variables (`OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_API_TOKEN`). |
| **Vector DB** | NumPy (Local) $\rightarrow$ `pgvector` / Qdrant (Enterprise) | In-memory matrix for local sub-10ms lookup; migration path to PostgreSQL `pgvector`. |
| **CAD Drafting** | `ezdxf` (Release R2010 DXF) | Pure Python, headless, no dependency on proprietary Autodesk Windows runtime. |
| **API Framework** | `FastAPI` + `Pydantic v2` | High-performance asynchronous REST API with automatic OpenAPI Swagger documentation. |
| **Containerization** | `Docker` + `Docker Compose` | Linux-based reproducible container image (`python:3.12-slim`) validated in cloud CI/CD. |
| **Version Control** | `Git` + `Git LFS` / `DVC` | Git for source code; Git LFS and DVC for multi-gigabyte raw standards and PDF caches. |
