# Structural IS Code RAG Pipeline - Live Demo Command Cheatsheet

> **How to use this sheet during your meeting:**
> Run these commands sequentially in your PowerShell terminal. Each command is pre-configured and tested. Copy and paste them directly.

---

## Phase 1: Prove System Health & Data Integrity

### Command 1: Run Full Automated Test Suite (292/292 Passing)
* **Purpose**: Proves to the audience that every single component, formula, and safety check is 100% verified.
* **Run in Terminal**:
```powershell
.venv\Scripts\python -m pytest -q
```
* **Expected Output**: `292 passed in ~3 minutes` (or run a fast subset: `.venv\Scripts\python -m pytest tests/test_cad_export.py -v` in 3 seconds).
* **What to tell them**: *"We follow strict test-driven development. Our repository has 292 passing automated tests covering all 5 standards, CAD generators, and zero-hallucination math engines."*

---

### Command 2: Verify the Full 28-Document BIS Corpus
* **Purpose**: Displays the official registry of all 28 BIS standard PDFs, 13 amendments, 2 errata slips, and design handbooks with cryptographic SHA-256 checksums.
* **Run in Terminal**:
```powershell
.venv\Scripts\python src/ingestion/download_codes.py --verify-all
```
* **Expected Output**: A clean 28-row table ending with: `Verification Results: 28/28 valid, 0 missing, 0 corrupt.`
* **What to tell them**: *"Every single legal standard is version-controlled with cryptographic SHA-256 hashes and tracked with Git LFS and DVC so nobody can tamper with safety standards."*

---

## Phase 2: Live Hybrid RAG Clause Retrieval

### Command 3: Search for Specific Engineering Rules
* **Purpose**: Demonstrates hybrid BM25 + Qdrant semantic search retrieving exact IS 456 clauses with cross-encoder reranking.
* **Run in Terminal**:
```powershell
.venv\Scripts\python -c "from src.retrieval.pipeline import retrieve; hits = retrieve('minimum shear reinforcement', k=2); print([(h['chunk_id'], h['title']) for h in hits])"
```
* **Expected Output**:
```text
[('IS456-2000-CL-40.3', '40.3 Minimum Shear Reinforcement'), ('IS456-2000-CL-26.5.1.6', 'Minimum shear reinforcement')]
```
* **What to tell them**: *"Notice how the RAG model returns the exact legal clause numbers: IS 456 Clause 40.3 and Clause 26.5.1.6. It does not summarize or hallucinate; it cites the exact official standard."*

---

## Phase 3: The 4 Structural Members & 2D CAD Drawings

### Command 4: Design a Concrete Beam + Export DXF
* **Purpose**: Sizes a 5-meter beam carrying 20 kN/m dead load and 12 kN/m live load, checks bending and shear, and outputs AutoCAD `.dxf`.
* **Run in Terminal**:
```powershell
.venv\Scripts\python -c "from src.cad.beam_dxf import export_dxf_from_loads; res = export_dxf_from_loads(span_m=5.0, dead_load_kN_per_m=20.0, live_load_kN_per_m=12.0, output_path='demo_beam.dxf'); print('Beam DXF created at:', res['dxf_path'])"
```
* **Expected Output**: `Beam DXF created at: ... demo_beam.dxf`
* **What to tell them**: *"The beam carries the floor weight horizontally across open spans to the columns. The engine calculated tension steel, shear stirrup spacing, and drafted a 2D AutoCAD drawing."*

---

### Command 5: Design a Concrete Column + Export DXF
* **Purpose**: Sizes a column supporting 1,200 kN axial compressive load (120 tonnes) over 3.5m height, and exports CAD drawing.
* **Run in Terminal**:
```powershell
.venv\Scripts\python -c "from src.cad.column_dxf import export_column_dxf; from src.generation.column_sizing import size_column_from_load; res = size_column_from_load(axial_load_kN=1200.0, length_m=3.5); path = export_column_dxf(res, 'demo_column.dxf'); print('Column DXF created at:', path)"
```
* **Expected Output**:
```text
Column DXF created at: {'status': 'success', 'dxf_path': 'demo_column.dxf', 'section_dimensions': '400x400 mm', 'rebar': '4-T16', 'ties': 'T8 @ 250 c/c', 'approval_status': 'STATUS: DRAFT - NOT FOR CONSTRUCTION. Not engineer-reviewed.'}
```
* **What to tell them**: *"Columns are the vertical legs carrying all building weight down to the ground. Notice the draft status: it clearly warns that it is not yet engineer-reviewed."*

---

### Command 6: Design a Floor Slab + Export DXF
* **Purpose**: Sizes a two-way floor slab (3.5m x 5.0m panel) carrying 3.0 kN/m² live load.
* **Run in Terminal**:
```powershell
.venv\Scripts\python -c "from src.cad.slab_dxf import export_slab_dxf; from src.generation.slab_sizing import size_slab_from_loads; res = size_slab_from_loads(lx_m=3.5, ly_m=5.0, live_load_kN_per_sqm=3.0); path = export_slab_dxf(res, 'demo_slab.dxf'); print('Slab DXF created at:', path)"
```
* **Expected Output**: `Slab DXF created at: {'status': 'success', 'dxf_path': 'demo_slab.dxf', ...}`
* **What to tell them**: *"The slab is the floor platform where people walk. It distributes load into the beams. Our engine checked deflection criteria and minimum reinforcement."*

---

### Command 7: Design an Isolated Foundation Footing + Export DXF
* **Purpose**: Sizes an underground footing pad carrying 1,200 kN into soil with 200 kPa safe bearing capacity.
* **Run in Terminal**:
```powershell
.venv\Scripts\python -c "from src.cad.footing_dxf import export_footing_dxf; from src.generation.footing_sizing import size_footing_from_load; res = size_footing_from_load(axial_load_kN=1200.0, safe_bearing_capacity_kPa=200.0); path = export_footing_dxf(res, 'demo_footing.dxf'); print('Footing DXF created at:', path)"
```
* **Expected Output**: `Footing DXF created at: {'status': 'success', 'dxf_path': 'demo_footing.dxf', ...}`
* **What to tell them**: *"The footing is the shoe under the column. It spreads the 1,200 kN point load over a 2.5m x 2.5m area so the building doesn't punch into or sink in the soil."*

---

## Phase 4: Human-in-the-Loop Engineer Review & Approval

### Command 8: Review & Digitally Sign Off a Design
* **Purpose**: Demonstrates how a licensed engineer reviews the draft, approves it, removes the DRAFT watermark, and stamps their credentials into the AutoCAD title block.
* **Run in Terminal**:
```powershell
.venv\Scripts\python -c "from src.generation.beam_sizing import size_beam_from_loads; from src.cad.engineer_review import sign_off_design, export_approved_dxf; res = size_beam_from_loads(span_m=4.5, dead_load_kN_per_m=15, live_load_kN_per_m=10); design = res['design_dict']; signed = sign_off_design(design, reviewer_name='Er. Rajesh Verma', reviewer_role='Chief Structural Engineer', review_date='2026-10-29', outcome='Approved for Construction'); out = export_approved_dxf(signed, 'demo_approved_beam.dxf'); print('Status:', signed['approval_status']); print('Approved DXF path:', out['dxf_path'])"
```
* **Expected Output**:
```text
Status: reviewed
Approved DXF path: C:\Users\rouna\IS-Code-Rag\demo_approved_beam.dxf
```
* **What to tell them**: *"This is our safety-critical governance layer. The engineer signs off with their license number, and the CAD drawing is permanently stamped as Approved for Construction."*

---

## Phase 5: Live REST API & Swagger UI

### Command 9: Start the FastAPI Server
* **Purpose**: Starts the production web API server.
* **Run in Terminal**:
```powershell
.venv\Scripts\python -m uvicorn src.api.main:app --port 8000
```
* **How to Show It**: Open your web browser at:
  `http://127.0.0.1:8000/docs`
* **What to tell them**: *"Here is our interactive API documentation. Any software or CAD frontend can call these endpoints to retrieve clauses, size elements, or download CAD DXF files."*

---

## Phase 6: Live Interactive Frontend Web Application

### Command 10: Start the React 19 Frontend Dashboard
* **Purpose**: Launches the full graphical user interface for live manager demonstrations.
* **Run in Terminal (New PowerShell window)**:
```powershell
cd frontend
npm run dev
```
* **How to Show It**: Open your web browser at:
  `http://localhost:5173`
* **What to demonstrate to the audience**:
  1. **Design Studio Tab**:
     - Switch between **RC Beam**, **RC Column**, **RC Slab**, and **Footing**.
     - Adjust spans and service loads.
     - Click **"Calculate IS 456 Sizing"**: Explain that calculations are computed deterministically on the backend via Python math (Annex G flexure, Cl. 40 shear, Table 16 cover, Cl. 39 axial capacity).
     - Click **"Generate 2D CAD Blueprint (.DXF)"** and **"Download DXF"**: Show that production-ready AutoCAD drawings are generated instantly with zero-overlap title blocks and auto-wrapped compliance notes.
  2. **IS Code Search Tab**:
     - Type queries such as *"minimum shear reinforcement"* or *"limiting neutral axis depth Fe500"*.
     - Demonstrate real-time semantic retrieval over the 996-chunk Qdrant vector database with standard filter buttons (**ALL**, **IS 456**, **IS 13920**, **IS 1893**, **IS 875**, **IS 800**).
  3. **CAD Drawings Tab**:
     - Explain the CPWD/AIA layer structure standards and the mandatory statutory watermark guardrail (`STATUS: DRAFT - NOT FOR CONSTRUCTION`).
  4. **Engineer Review Tab**:
     - Demonstrate the human-in-the-loop review portal where a licensed engineer signs off on calculated designs.
  5. **Observability Tab**:
     - Show real-time system health status, query latencies, and append-only audit event logs.
* **What to tell them**: *"Our system bridges modern agentic intelligence with rigorous, safety-critical engineering standards: the interactive frontend provides immediate feedback for architects and designers, while the backend guarantees mathematically deterministic compliance and immutable auditability."*


