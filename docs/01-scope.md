# Project Scope & Engineering Specification

## 1. Executive Summary & Objective

This project is a draft pilot implementation of a **Retrieval-Augmented Generation (RAG) and Deterministic Structural Design System** for structural Indian Standards, specifically **IS 456:2000** (*Plain and Reinforced Concrete - Code of Practice*).

The primary objective is automated preliminary structural sizing, reinforcement detailing, multi-stage clause retrieval, and 2D CAD drawing generation for **Reinforced Concrete (RC) Beams**. The system passes the implemented IS 456 beam detailing checks only, is not a full design check, and a structural engineer must review every result.

---

## 2. Core Architectural Principle: Decoupled Deterministic Engineering

A foundational requirement of this project is the strict separation between **statistical AI retrieval** and **deterministic structural engineering calculations**:

1. **Deterministic Calculation & Validation Engine**:
   - All structural math—including flexural capacity ($M_u, M_{u,lim}, A_{st}$), shear capacity ($\tau_v, \tau_c, \tau_{c,max}, V_{us}, s_v$), detailing limits ($A_{s,min}, A_{s,max}$), and durability cover—is executed deterministically in pure Python code against verified JSON tables.
   - **Deterministic Calculations**: Large Language Models (LLMs) are never allowed to invent, estimate, or alter structural design formulas or safety factors.
2. **AI & RAG Retrieval Engine**:
   - Language models and vector search engines are used exclusively for semantic query interpretation, relevant code clause retrieval, and grounded engineering explanations citing verified clause citations.
3. **Automated 2D CAD Engine**:
   - Validated engineering parameters are mapped deterministically into CAD geometry (`ezdxf`), producing preliminary 2D DXF drawings.

---

## 3. Codified Provisions Implemented (IS 456:2000)

The system covers 23 human-verified chunks across 4 major design domains:

### A. Limit State of Collapse: Flexure
- **Annex G, Clause G-1.1(a)**: Depth of neutral axis formula $x_u/d = \frac{0.87 f_y A_{st}}{0.36 f_{ck} b d}$.
- **Annex G, Clause G-1.1(b)**: Factored moment of resistance $M_u = 0.87 f_y A_{st} d \left(1 - \frac{A_{st} f_y}{b d f_{ck}}\right)$ for under-reinforced singly reinforced beams ($x_u \le x_{u,max}$).
- **Annex G, Clause G-1.1(c)**: Limiting moment of resistance $M_{u,lim} = 0.36 \frac{x_{u,max}}{d} \left(1 - 0.42 \frac{x_{u,max}}{d}\right) b d^2 f_{ck}$.
- **Annex G, Clause G-1.1(d)**: Mandatory section redesign condition when $x_u > x_{u,max}$.
- **Annex G, Clause G-1.2**: Doubly reinforced section formulas (compression steel $A_{sc}$ and moment balance).
- **Clause 38.1 Note**: Limiting depth of neutral axis ratio ($x_{u,max}/d$):
  - Fe 250: $0.53$
  - Fe 415: $0.48$
  - Fe 500: $0.46$

### B. Limit State of Collapse: Shear
- **Clause 40.1**: Factored nominal shear stress $\tau_v = \frac{V_u}{b d}$.
- **Clause 40.2.3 & Table 20**: Absolute physical ceiling $\tau_{c,max}$ (M15: 2.5, M20: 2.8, M25: 3.1, M30: 3.5, M35: 3.7, M40+: 4.0 N/mm²). If $\tau_v > \tau_{c,max}$, the cross-section must be enlarged.
- **Clause 40.3 & Table 19**: Design shear strength of concrete $\tau_c$ based on tension steel percentage $p_t = \frac{100 A_{st}}{b d}$ and concrete grade (78 verified values).
- **Clause 40.4**: Net shear to be carried by shear reinforcement $V_{us} = V_u - \tau_c b d$.
- **Clause 40.4(a)**: Vertical stirrup shear resistance $V_{us} = \frac{0.87 f_y A_{sv} d}{s_v}$ ($f_y$ capped at $415\text{ N/mm²}$ per code).

### C. Requirements of Reinforcement & Detailing
- **Clause 26.5.1.1(a)**: Minimum tension reinforcement $\frac{A_s}{b d} \ge \frac{0.85}{f_y}$.
- **Clause 26.5.1.1(b)**: Maximum tension reinforcement $A_s \le 0.04 b D$.
- **Clause 26.5.1.2**: Maximum compression reinforcement $A_{sc} \le 0.04 b D$.
- **Clause 26.5.1.3**: Side face reinforcement for web depth $D > 750\text{ mm}$ ($0.1\%$ web area distributed equally).
- **Clause 26.5.1.4**: Transverse reinforcement enclosing longitudinal bars.
- **Clause 26.5.1.5**: Maximum stirrup spacing limit $s_v \le \min(0.75d, 300\text{ mm})$.
- **Clause 26.5.1.6**: Minimum shear reinforcement formula $\frac{A_{sv}}{b s_v} \ge \frac{0.4}{0.87 f_y}$.
- **Clause 26.5.1.7**: Closed stirrups spacing for members subject to torsion.
- **Clause 26.5.1.8**: Flange reinforcement in T-beams and L-beams.

### D. Durability & Concrete Cover
- **Table 16 (Clause 26.4.2)**: Nominal concrete cover based on environmental exposure:
  - Mild: 20 mm
  - Moderate: 30 mm
  - Severe: 45 mm (reducible by 5 mm for M35+)
  - Very Severe: 50 mm (reducible by 5 mm for M35+)
  - Extreme: 75 mm

---

## 4. Current Stack & Tooling

- **Language Runtime**: Python 3.11 / 3.14 compatible
- **Document Ingestion**: PyMuPDF (`fitz`) for precise PDF page extraction and inspection
- **Dense Embedding Model**: `BAAI/bge-small-en-v1.5` (normalized cosine embeddings)
- **Lexical Search**: `rank-bm25` (custom tokenizer preserving clause numbers and decimals)
- **Reranker Model**: `BAAI/bge-reranker-base` (Cross-Encoder)
- **Vector Storage**: File-backed normalized NumPy matrices (`embeddings.npy`, `embedding_ids.json`)
- **API Framework**: FastAPI with lifespan startup preloading and Uvicorn
- **CAD Drafting Engine**: `ezdxf` (AC1024 standard DXF output)
- **Testing Framework**: `pytest` (123 comprehensive tests)

---

## 5. Working Assumptions & Practical Rules

1. **Member Type**: Simply supported rectangular RC beams subjected to uniformly distributed loads (Dead Load + Live Load + self-weight).
2. **Partial Safety Factors**: Factored design loads use $\gamma_f = 1.5$ ($w_u = 1.5(DL + LL + \text{self-weight})$).
3. **Bar Detailing**:
   - Tension bars evaluated across standard sizes: 12 mm, 16 mm, 20 mm, 25 mm, 32 mm.
   - Clear spacing per IS 456 Cl. 26.3.2(a) requires clear gap $\ge \max(\phi_{\text{bar}}, \text{aggregate size} + 5\text{ mm})$. A 20 mm nominal maximum aggregate size (giving a 25 mm clearance floor) is assumed unless an alternative is provided.
   - Top bars provided as 2 hanger bars (minimum 10 mm or 12 mm) for stirrup support.
4. **Practical Stirrup Selection**:
   - Sizing progressively evaluates 8 mm, 10 mm, then 12 mm two-legged stirrups.
   - Sizing selects the first diameter yielding a spacing $\ge 100\text{ mm}$ (practical pouring floor).
   - If spacing cannot reach 100 mm without exceeding $\tau_{c,max}$, the status returns `needs_review` with an instruction to enlarge the concrete cross-section.
   - Spacing is rounded down to the nearest 5 mm for constructability and drawn symmetrically along the beam span.

---

## 6. Out of Scope (Future Phases)

The following items are outside the current beam design phase and planned for future expansions:
1. **Flanged Beams**: T-beams and L-beams (neutral axis falling in web vs. flange, Annex G-2).
2. **Alternative Member Types**:
   - Solid two-way and flat slabs (IS 456 Cl. 26.5.2, Cl. 24).
   - Compression members / Columns (IS 456 Cl. 26.5.3, Cl. 39).
   - Isolated and combined footings (IS 456 Cl. 34).
3. **Ductile Detailing**: Earthquake-resistant detailing conforming to **IS 13920:2016**.
4. **Bent-up Bars & Inclined Stirrups**: Current shear detailing strictly implements vertical stirrup ties.

---

## 7. Professional Engineering Disclaimer

The designs, calculations, and drawings generated by this system are automated self-consistency checks and arithmetic verifications of IS 456:2000 codified rules. **They do not replace the judgment of a qualified structural engineer.** A licensed structural engineer must review and approve all structural member sizes, reinforcement detailing, and construction drawings prior to fabrication and placement.
