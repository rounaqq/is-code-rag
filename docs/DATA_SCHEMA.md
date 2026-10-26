Status: draft pilot. Passes the implemented IS 456 beam detailing checks only. Not engineer-reviewed.

# Data Schema and Dataset Reference

## 1. Overview

This document details the data schemas, storage formats, and structures of all digitized clauses, tabular data, vector indices, and evaluation sets present in the repository.

Data ingestion follows a digitize-and-validate pattern: clauses, notes, and numeric tables are digitized from the printed standard into structured JSON files under `data/processed/`, which are subsequently synthesized into a unified JSON Lines file (`chunks.jsonl`) for retrieval and embedding generation.

---

## 2. Processed Clause and Table JSON Files (`data/processed/`)

The repository contains seven primary structured JSON data files in `data/processed/`.

### 2.1 `is456_cl_26_5_1.json`
Contains 9 individual detailing provisions digitized from IS 456:2000 Clause 26.5.1 ("Beams"):
- **Top-Level Structure**: An array of 9 clause objects.
- **Object Schema**:
  - `code_id` (string): `"IS 456"`
  - `edition_year` (integer): `2000`
  - `clause_number` (string): Specific clause identifier (`"26.5.1.1(a)"` through `"26.5.1.8"`)
  - `clause_title` (string): Standard heading
  - `title_ocr_raw` (string or null): Raw OCR heading text
  - `page_number` (array of integers): Physical PDF page references per item:
    - `26.5.1.1(a)`: `[59, 60]`
    - `26.5.1.1(b)`: `[60]`
    - `26.5.1.2`: `[60]`
    - `26.5.1.3`: `[60]`
    - `26.5.1.4`: `[60]`
    - `26.5.1.5`: `[60, 61]`
    - `26.5.1.6`: `[61]`
    - `26.5.1.7`: `[61]`
    - `26.5.1.8`: `[61]`
  - `raw_text` (string): Unmodified extracted text
  - `cleaned_text` (string): Cleaned clause text
  - `cross_references` (array of strings): Referenced clauses or tables per item:
    - `26.5.1.1(a)`: `[]`
    - `26.5.1.1(b)`: `[]`
    - `26.5.1.2`: `["26.5.3.2"]`
    - `26.5.1.3`: `[]`
    - `26.5.1.4`: `[]`
    - `26.5.1.5`: `[]`
    - `26.5.1.6`: `[]`
    - `26.5.1.7`: `["41", "B-6", "26.5.1.3"]`
    - `26.5.1.8`: `["23.1.1(b)"]`
  - `applicable_components` (array of strings): Structural member types (`["beams"]`)
  - `needs_manual_check` (boolean): Flag for human review
  - `verified` (boolean): Human validation confirmation flag
  - `verified_by` (string): Reviewer attribution
  - `formula_verified` (string or null): Formula confirmation note
  - `verified_text` (string): Cleaned text confirmed against printed standard pages
  - `notes`: None (note count: 0)
- **Clauses Covered**:
  1. `26.5.1.1(a)`: Minimum tension reinforcement ($A_s / (b d) \ge 0.85 / f_y$)
  2. `26.5.1.1(b)`: Maximum tension reinforcement ($0.04 b D$)
  3. `26.5.1.2`: Maximum compression reinforcement ($0.04 b D$)
  4. `26.5.1.3`: Side face reinforcement for web depth exceeding 750 mm ($0.1\%$ web area, spaced $\le 300\text{ mm}$)
  5. `26.5.1.4`: Transverse reinforcement enclosure around tension and compression bars
  6. `26.5.1.5`: Maximum spacing of shear stirrups ($\le 0.75 d$ or $300\text{ mm}$)
  7. `26.5.1.6`: Minimum shear reinforcement ($A_{sv} / (b s_v) \ge 0.4 / (0.87 f_y)$)
  8. `26.5.1.7`: Torsion reinforcement detailing and closed stirrups spacing
  9. `26.5.1.8`: Transverse reinforcement in flanges of T-beams and L-beams

### 2.2 `is456_table_16.json`
Represents IS 456:2000 Table 16 ("Nominal Cover to Meet Durability Requirements"):
- **Top-Level Structure**: Object containing metadata, table rows, and explanatory notes.
- **Fields**:
  - `code_id` (string): `"IS 456"`
  - `edition_year` (integer): `2000`
  - `table_number` (integer): `16`
  - `title` (string): `"Nominal Cover to Meet Durability Requirements"`
  - `clause_reference` (string): `"26.4.2"`
  - `rows` (array of objects): Exposure conditions and required cover:
    - `exposure` (string): `"Mild"`, `"Moderate"`, `"Severe"`, `"Very severe"`, `"Extreme"`
    - `nominal_cover_mm` (integer): `20`, `30`, `45`, `50`, `75`
  - `notes` (array of strings, note count: 3):
    1. `"For main reinforcement up to 12 mm diameter bar for mild exposure the nominal cover may be reduced by 5 mm."`
    2. `"Unless specified otherwise, actual concrete cover should not deviate from the required nominal cover by +10 mm / 0 mm (printed as +10 over 0)."`
    3. `"For exposure condition 'severe' and 'very severe', reduction of 5 mm may be made, where concrete grade is M35 and above."`
  - `page_number` (integer): `60`
  - `verified` (boolean): `true`
  - `verified_by` (string): Manual check attribution against cropped page scan

### 2.3 `is456_table_19.json`
Represents IS 456:2000 Table 19 ("Design Shear Strength of Concrete, $\tau_c$, $N/mm^2$"):
- **Top-Level Structure**: Object defining the matrix of concrete shear strengths.
- **Fields**:
  - `code_id` (string): `"IS 456"`
  - `edition_year` (integer): `2000`
  - `table_number` (integer): `19`
  - `title` (string): `"Design Shear Strength of Concrete"`
  - `symbol` (string): `"tau_c"`
  - `units` (string): `"N/mm2"`
  - `clause_references` (array of strings, exact list of 8 references): `["40.2.1", "40.2.2", "40.3", "40.4", "40.5.3", "41.3.2", "41.3.3", "41.4.3"]`
  - `row_variable` (string): `"100*A_s/(b*d)"`
  - `column_headings` (array of strings): `["M15", "M20", "M25", "M30", "M35", "M40 and above"]`
  - `rows` (array of 13 objects):
    - Values for `pt_value` from `0.15` to `3.0` (labels: `"<=0.15"` through `"3.00 and above"`)
    - `tau_c` (object): Map of concrete grade to shear strength float value
  - `notes` (array of strings, note count: 1):
    1. `"The term A_s is the area of longitudinal tension reinforcement which continues at least one effective depth beyond the section being considered except at support where the full area of tension reinforcement may be used provided the detailing conforms to 26.2.2 and 26.2.3."`
  - `page_number` (integer): `86`
  - `verified` (boolean): `true`

### 2.4 `is456_table_20.json`
Represents IS 456:2000 Table 20 ("Maximum Shear Stress, $\tau_{c,\max}$, $N/mm^2$"):
- **Top-Level Structure**: Object defining maximum permissible shear stresses.
- **Fields**:
  - `code_id` (string): `"IS 456"`
  - `edition_year` (integer): `2000`
  - `table_number` (integer): `20`
  - `title` (string): `"Maximum Shear Stress"`
  - `symbol` (string): `"tau_c_max"`
  - `units` (string): `"N/mm2"`
  - `clause_references` (array of strings, exact list of 4 references): `["40.2.3", "40.2.3.1", "40.5.1", "41.3.1"]`
  - `rows` (array of 6 objects):
    - `grade` (string): Concrete grade (`"M15"` through `"M40 and above"`)
    - `tau_c_max` (float): Limiting value (`2.5`, `2.8`, `3.1`, `3.5`, `3.7`, `4.0`)
  - `notes`: None (note count: 0)
  - `page_number` (integer): `86`
  - `printed_page_number` (integer): `73`
  - `verified` (boolean): `true`

### 2.5 `is456_xu_max_table.json`
Represents the limiting depth of neutral axis table from the Note under Clause 38.1:
- **Top-Level Structure**: Object mapping yield strength to neutral axis limiting ratios.
- **Fields**:
  - `code_id` (string): `"IS 456"`
  - `edition_year` (integer): `2000`
  - `clause_reference` (string): `"38.1"`
  - `title` (string): `"Limiting values of the depth of neutral axis"`
  - `rows` (array of 3 objects):
    - `fy_N_per_mm2` (integer): Characteristic yield strength (`250`, `415`, `500`)
    - `xu_max_over_d` (float): Ratio ($0.53$, $0.48$, $0.46$)
  - `notes`: None (note count: 0)
  - `page_number` (integer): `83`
  - `printed_page_number` (integer): `70`
  - `verified` (boolean): `true`

### 2.6 `is456_annex_g.json`
Represents Annex G ("Moments of Resistance for Rectangular and T-Sections"):
- **Top-Level Structure**: Object containing flexural formulas for rectangular sections.
- **Fields**:
  - `code_id` (string): `"IS 456"`
  - `edition_year` (integer): `2000`
  - `annex` (string): `"G"`
  - `clause_reference` (string): `"38.1"`
  - `title` (string): `"Moments of resistance for rectangular and T-sections"`
  - `page_number` (integer): `109`
  - `printed_page_number` (integer): `96`
  - `verified` (boolean): `true`
  - `items` (array of 6 objects):
    - `G-1.1(a)`: neutral axis depth formula ($x_u/d = 0.87 f_y A_{st} / (0.36 f_{ck} b d)$)
    - `G-1.1(b)`: moment of resistance formula for $x_u/d \le \text{limiting value}$
    - `G-1.1(c)`: limiting moment of resistance formula $M_{u,\lim}$
    - `G-1.1(d)`: redesign condition when $x_u/d > \text{limiting value}$
    - `G-1.2`: doubly reinforced section formulas
    - `G-2`: flanged sections (marked as `"not implemented"`)
  - `notes`: None (note count: 0)

### 2.7 `is456_cl_40.json`
Represents Clause 40 ("Limit State of Collapse: Shear"):
- **Top-Level Structure**: Object containing shear design rules.
- **Fields**:
  - `code_id` (string): `"IS 456"`
  - `edition_year` (integer): `2000`
  - `clause_reference` (string): `"40"`
  - `title` (string): `"Limit state of collapse: shear"`
  - `page_number` (array of integers): `[85, 86]`
  - `printed_pages` (array of integers): `[72, 73]`
  - `verified` (boolean): `true`
  - `items` (array of 6 objects):
    - `40.1`: Nominal shear stress equation $\tau_v = V_u / (b d)$
    - `40.2.3`: Maximum shear stress ceiling $\tau_{c,\max}$ from Table 20
    - `40.3`: Minimum shear reinforcement condition when $\tau_v \le \tau_c$
    - `40.4`: Design of shear reinforcement for excess shear $V_{us} = V_u - \tau_c b d$
    - `40.4(a)`: Vertical stirrup resistance equation
    - `not_implemented`: Marker covering unhandled provisions
  - `not_implemented` (array of 6 strings): `["inclined stirrups", "bent-up bars", "slabs (40.2.1.1)", "axial compression (40.2.2)", "beams of varying depth (40.1.1)", "enhanced shear near supports (40.5)"]`
  - `notes`: None (note count: 0)

### 2.8 `is456_cl_19_2.json`
Represents Clause 19.2 ("Dead Loads and Unit Weights"):
- **Top-Level Structure**: Object containing unit weights of concrete.
- **Fields**:
  - `code_id` (string): `"IS 456"`
  - `edition_year` (integer): `2000`
  - `clause_reference` (string): `"19.2"`
  - `title` (string): `"Dead Loads and Unit Weights"`
  - `page_number` (integer): `45`
  - `printed_page_number` (integer): `32`
  - `verified` (boolean): `true`
  - `items` (array of 2 objects):
    - `19.2`: Dead load basis
    - `19.2.1`: Unit weight of plain concrete ($24.0\text{ kN/m}^3$) and reinforced concrete ($25.0\text{ kN/m}^3$)

### 2.9 `is456_cl_22_2.json`
Represents Clause 22.2 ("Effective Span"):
- **Top-Level Structure**: Object containing effective span definitions.
- **Fields**:
  - `code_id` (string): `"IS 456"`
  - `edition_year` (integer): `2000`
  - `clause_reference` (string): `"22.2"`
  - `title` (string): `"Effective Span"`
  - `page_number` (array of integers): `[47, 48]`
  - `printed_pages` (array of integers): `[34, 35]`
  - `verified` (boolean): `true`
  - `items` (array of 4 objects):
    - `22.2(a)`: Simply supported beam effective span ($\min(\text{clear span} + d, \text{clear span} + \text{support width})$)
    - `22.2(b)`: Continuous beam or slab
    - `22.2(c)`: Cantilever
    - `22.2(d)`: Frames

### 2.10 `is456_cl_23_2.json`
Represents Clause 23.2 ("Control of Deflection"):
- **Top-Level Structure**: Object containing span-to-depth basic ratios and modification factors.
- **Fields**:
  - `code_id` (string): `"IS 456"`
  - `edition_year` (integer): `2000`
  - `clause_reference` (string): `"23.2"`
  - `title` (string): `"Control of Deflection"`
  - `page_number` (array of integers): `[50, 51]`
  - `printed_pages` (array of integers): `[37, 38]`
  - `verified` (boolean): `true`
  - `basic_span_to_depth_ratios` (object): `{"cantilever": 7.0, "simply_supported": 20.0, "continuous": 26.0}`
  - `spans_above_10m_rule` (string): Rule multiplying basic ratio by $10 / \text{span}$
  - `fs_formula` (string): `0.58 * fy * (Ast_required / Ast_provided)`
  - `modification_factor_formula` (string): Approximate curve fit, not from IS 456, capped at 2.0 (unclamped value reported alongside). Fig. 4 covers $p_t \in [0, 3.0]$ and $f_s \in [120, 290]\text{ N/mm}^2$: sets `needs_review` if outside; clamps $f_s = 120\text{ N/mm}^2$ with note if $f_s < 120$.

### 2.11 `is456_cl_26_2.json`
Represents Clause 26.2 ("Development of Stress in Reinforcement"):
- **Top-Level Structure**: Object containing development length and bond stress rules.
- **Fields**:
  - `code_id` (string): `"IS 456"`
  - `edition_year` (integer): `2000`
  - `clause_reference` (string): `"26.2"`
  - `title` (string): `"Development of Stress in Reinforcement"`
  - `page_number` (array of integers): `[55, 56]`
  - `printed_pages` (array of integers): `[42, 43]`
  - `verified` (boolean): `true`
  - `items` (array of 3 objects):
    - `26.2.1`: Development length formula $L_d = (\phi \cdot \sigma_s) / (4 \tau_{bd})$, with $\sigma_s = 0.87 f_y$
    - `26.2.1.1`: Design bond stress table for plain bars in tension (M20: 1.2, M25: 1.4, M30: 1.5, M35: 1.7, M40+: 1.9 N/mm²), increased by 60% for deformed bars and 25% for compression
    - `26.2.3.3`: Anchoring tension reinforcement at support ($L_d / 3$)

### 2.12 `is456_cl_26_3_2.json`
Represents Clause 26.3.2 ("Minimum distance between individual bars"):
- **Top-Level Structure**: Object containing minimum horizontal clearance rules between parallel main bars.
- **Fields**:
  - `code_id` (string): `"IS 456"`
  - `edition_year` (integer): `2000`
  - `clause_reference` (string): `"26.3.2"`
  - `title` (string): `"Minimum distance between individual bars"`
  - `page_number` (integer): `58`
  - `printed_page_number` (integer): `45`
  - `verified` (boolean): `true`
  - `verified_by` (string): `"Rounaq, manual check against page_058.png"`
  - `items` (array): Contains `26.3.2(a)` requiring clear horizontal distance $\ge \max(\text{bar\_dia}, \text{aggregate size} + 5\text{ mm})$.
  - `note` (string): Aggregates may be reduced around congested reinforcement.
  - `not_implemented` (array): Bundled bars (26.3.1), bars in more than one layer, 26.3.2(b).

---

## 3. Unified Chunk File (`data/processed/chunks.jsonl`)

The build script `src/chunking/build_chunks.py` compiles the individual JSON files into 23 chunks stored in `data/processed/chunks.jsonl`. Each line is an independent JSON object with the following schema:

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `chunk_id` | string | Unique identifier (e.g., `IS456-2000-CL-26.5.1.1(a)`, `IS456-2000-TABLE-16`) |
| `chunk_type` | string | Either `"clause"` or `"table"` |
| `code_id` | string | Code name (`"IS 456"`) |
| `edition_year` | integer | Code publication year (`2000`) |
| `clause_number` | string or null | Subclause identifier or null for tables |
| `table_number` | integer or null | Table number or null for clauses |
| `title` | string | Human-readable clause or table heading |
| `context_path` | string or null | Breadcrumb path within the standard hierarchy |
| `page_number` | array of integers | Physical pages in the standard document |
| `text` | string | Rendered text used for embeddings, BM25, and LLM context |
| `cross_references` | array of strings | Clauses or tables explicitly cited within the chunk |
| `citation` | string | Standardized legal citation string |
| `verified` | boolean | Confirmation flag against physical printed standard pages |

### Breakdown of the 23 Chunks:
- **Clause 26.5.1**: 9 chunks (`IS456-2000-CL-26.5.1.1(a)` through `IS456-2000-CL-26.5.1.8`)
- **Table 16**: 1 chunk (`IS456-2000-TABLE-16`, page `[60]`)
- **Table 19**: 1 chunk (`IS456-2000-TABLE-19`, page `[86]`)
- **Table 20**: 1 chunk (`IS456-2000-TABLE-20`, page `[86]`)
- **Table xu_max**: 1 chunk (`IS456-2000-TABLE-XU-MAX-38.1`, page `[83]`)
- **Annex G**: 5 chunks (`IS456-2000-ANNEX-G-G-1.1(a)` through `G-1.1(d)`, and `G-1.2`, page `[109]`)
- **Clause 40**: 5 chunks (`IS456-2000-CL-40.1`, `40.2.3`, `40.3`, `40.4`, `40.4(a)`, page `[85, 86]`)

---

## 4. Vector and Index Files

- **`data/processed/embeddings.npy`**: Binary NumPy array of shape `(23, 384)` containing dense vector representations produced by `BAAI/bge-small-en-v1.5`. Vectors are L2-normalized.
- **`data/processed/embedding_ids.json`**: An ordered array of 23 chunk ID strings mapping each row index of `embeddings.npy` to its corresponding `chunk_id`.

---

## 5. Evaluation Data (`data/eval/`)

### 5.1 Retrieval Evaluation Queries (`data/eval/questions.json`)
The search evaluation results come from 19 self-written questions in `data/eval/questions.json`.
Each record maps a natural language structural engineering query to its target `chunk_id`:
```json
[
  {
    "question": "minimum tension reinforcement in a beam",
    "expected_chunk_id": "IS456-2000-CL-26.5.1.1(a)"
  },
  ...
]
```

### 5.2 Structural Design Scenarios (`data/eval/structural_design_scenarios.json`)
Contains 5 parametric scenarios used to test the deterministic beam sizing engine across realistic spans, loads, and exposure conditions:
- `beam_residential_3m`: 3.0 m span, DL 12 kN/m, LL 4 kN/m, M20, Fe415, Mild exposure.
- `beam_office_5m`: 5.0 m span, DL 20 kN/m, LL 8 kN/m, M25, Fe500, Moderate exposure.
- `beam_commercial_6m`: 6.0 m span, DL 25 kN/m, LL 12 kN/m, M25, Fe500, Moderate exposure.
- `beam_transfer_heavy_4m`: 4.0 m span, DL 45 kN/m, LL 25 kN/m, M30, Fe500, Moderate exposure.
- `beam_industrial_7m`: 7.0 m span, DL 28 kN/m, LL 15 kN/m, M30, Fe500, Severe exposure.

---

## 6. Engineering Assumptions

The following parameters and selection rules are not derived from the IS 456 pages and are included in the processing and sizing schemas as assumptions:

1. **Assumption: Load factor**: Service loads are multiplied by a fixed factor of 1.5 ($w_u = 1.5(DL + LL)$) per Table 18.
2. **Assumption: Default support width**: Effective span is calculated per Cl. 22.2(a) as $\min(\text{clear span} + d, \text{clear span} + \text{support width})$, with support bearing width defaulted to an assumed value of 300 mm when not provided by the user. (Unit weight of reinforced concrete is verified as 25.0 kN/m³ per Cl. 19.2.1).
3. **Assumption: Preliminary depth guess**: Preliminary depth is estimated as $\text{span} / 14$ rounded up to 25 mm, and total depth $D = d + \text{cover} + 25\text{ mm}$ rounded up to 25 mm. The actual effective depth $d_{\text{actual}} = D - \text{cover} - \phi_{\text{stirrup}} - \phi_{\text{bar}} / 2$ is subsequently recomputed from the chosen rebar diameters.
4. **Assumption: Stirrup sizes tried**: Stirrup diameters are evaluated strictly across 8 mm, 10 mm, and 12 mm.
5. **Assumption: Minimum spacing**: A minimum spacing threshold of 100 mm is enforced; spacing below 100 mm triggers `needs_review`.
6. **Assumption: Rounding to 5 mm**: Stirrup spacing is rounded down to the nearest 5 mm multiple for constructability.
7. **Assumption: Table 19 row rule**: For concrete shear strength $\tau_c$, the lookup selects the row where $p_t \le \text{calculated } p_t$ without linear interpolation (using row 1 if $p_t < 0.15$ and the last row if $p_t \ge 3.0$).
8. **Assumption: Deflection modification factor F1**: The tension modification factor $F_1$ is evaluated using an approximate curve fit, not from IS 456 (Fig. 4 has not yet been digitized from the page). Deflection check results are indicative only. Fig. 4 covers $p_t$ from 0 to 3.0 and $f_s$ from 120 to 290 N/mm²: if $p_t > 3.0$ or $f_s > 290\text{ N/mm}^2$, status is set to `needs_review` with the note "Outside the range of Fig. 4"; if $f_s < 120\text{ N/mm}^2$, $f_s = 120\text{ N/mm}^2$ is used and noted. Upper limit on $F_1$ is 2.0 with no lower limit, and no lower bound on $p_t$.
9. **Assumption: 20 mm nominal maximum aggregate size**: Per Cl. 26.3.2(a), horizontal clear distance between main bars must be at least $\max(\phi_{\text{bar}}, \text{aggregate size} + 5\text{ mm})$. A 20 mm nominal maximum aggregate size (giving a 25 mm clearance floor) is assumed unless an alternative value is explicitly provided.

---

## 7. Not implemented

The following capabilities, member types, standards, and data processing mechanisms are not implemented in this repository:
- other IS codes
- columns
- slabs
- footings
- DWG
- amendment tracking
- incremental updates
- doubly reinforced and T-beams
- engineer feedback loop
- Docker
- CI/CD
- faithfulness and answer-relevancy evaluation
- the LLM not connected to the sizing flow
- retrieval not used by the sizing code
