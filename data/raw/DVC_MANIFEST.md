# DVC (Data Version Control) & Git LFS Storage Manifest

> **Scope**: Step 2: Data Acquisition & Collection  
> **Corpus Version**: 2.0 (Complete Multi-Standard Structural Engineering Corpus)  
> **Repository**: [rounaqq/is-code-rag](https://github.com/rounaqq/is-code-rag)

---

## 1. Storage Architecture Overview

To prevent Git repository bloat when storing large multi-megabyte official Indian Standard PDFs, amendments, errata, and supplementary handbooks, we implement a two-tiered version control strategy:

1. **Git LFS (Large File Storage)**:  
   Configured in [`.gitattributes`](file:///c:/Users/rouna/IS-Code-Rag/.gitattributes) for binary assets (`*.pdf`, `*.dwg`, `*.npy`, `*.pkl`). Large files are replaced with lightweight text pointer files in GitHub commits.
2. **DVC (Data Version Control)**:  
   **Initialized** in this repository (`.dvc/`) for versioning the raw standards directory and embedding matrices across cloud environments. Each acquired PDF has a corresponding `<name>.pdf.dvc` pointer file committed to Git, while the PDF content itself lives in the DVC cache and is synced to the configured remote.

### Current DVC Configuration

| Setting | Value |
| :--- | :--- |
| DVC version | `3.67.1` |
| DVC config | `.dvc/config` |
| Default remote | `localremote` |
| Remote URL (local/dev) | `../data/dvc_remote` |
| Tracked artifacts | **28 PDFs (~91.1 MB)** across standards, amendments, errata & supplementary design examples |

> **Production remote**: for cloud/CI deployments, point the remote at object storage instead of the local directory:
> ```bash
> dvc remote add -d storageremote s3://my-is-code-rag-storage/data/ && dvc push
> ```

---

## 2. Complete Corpus Manifest (28 Documents)

All documents are acquired, validated as `%PDF-` files, and recorded with SHA-256 checksums in [`data/raw/registry.json`](file:///c:/Users/rouna/IS-Code-Rag/data/raw/registry.json).

### 2.1 Base Indian Standards (7 Documents)

| Standard / Document | Target File | File Size | Upstream Source | Verification Status |
| :--- | :--- | :--- | :--- | :--- |
| **IS 456:2000** | `data/raw/is_456_2000.pdf` | 7.10 MB | BIS / Public.Resource.Org | Verified (SHA-256) |
| **IS 13920:2016** | `data/raw/is_13920_2016.pdf` | 1.52 MB | BIS / Public.Resource.Org | Verified (SHA-256) |
| **IS 875 (Part 1):1987** | `data/raw/is_875_part_1_1987.pdf` | 1.78 MB | BIS / Public.Resource.Org | Verified (SHA-256) |
| **IS 875 (Part 2):1987** | `data/raw/is_875_part_2_1987.pdf` | 1.05 MB | BIS / Public.Resource.Org | Verified (SHA-256) |
| **IS 875 (Part 3):2015** | `data/raw/is_875_part_3_2015.pdf` | 9.12 MB | BIS / Public.Resource.Org | Verified (SHA-256) |
| **IS 1893 (Part 1):2016** | `data/raw/is_1893_part_1_2016.pdf` | 4.32 MB | BIS / Public.Resource.Org | Verified (SHA-256) |
| **IS 800:2007** | `data/raw/is_800_2007.pdf` | 10.85 MB | BIS / Public.Resource.Org | Verified (SHA-256) |

### 2.2 Supplementary BIS Handbooks (3 Documents)

| Standard / Document | Target File | File Size | Upstream Source | Verification Status |
| :--- | :--- | :--- | :--- | :--- |
| **SP:16:1980** | `data/raw/sp_16_1980.pdf` | 26.42 MB | BIS / Public.Resource.Org | Verified (Design Charts) |
| **SP:34:1987** | `data/raw/sp_34_1987.pdf` | 16.38 MB | BIS / Public.Resource.Org | Verified (Detailing Handbook) |
| **SP:24:1983** | `data/raw/sp_24_1983.pdf` | 12.31 MB | BIS / Public.Resource.Org | Verified (Explanatory Handbook) |

### 2.3 Official BIS Amendments (13 Documents)

| Code / Amendment | Target File | Issue Date | Key Affected Clauses | Verification Status |
| :--- | :--- | :--- | :--- | :--- |
| **IS 456:2000 AMD 1** | `data/raw/amendments/is_456_2000_amendment_1.pdf` | June 2001 | Cl. 5.3, Table 2, Table 5, Cl. 26.5.1.1(a) | Verified (SHA-256) |
| **IS 456:2000 AMD 2** | `data/raw/amendments/is_456_2000_amendment_2.pdf` | September 2002 | Cl. 5.1.1, Table 16, Cl. 40.2.3 | Verified (SHA-256) |
| **IS 456:2000 AMD 3** | `data/raw/amendments/is_456_2000_amendment_3.pdf` | August 2004 | Cl. 5.2.1, Table 5, Cl. 26.5.1.5, Table 19 | Verified (SHA-256) |
| **IS 456:2000 AMD 4** | `data/raw/amendments/is_456_2000_amendment_4.pdf` | May 2013 | Cl. 6.1, Table 2 (M65-M100), Table 20 | Verified (SHA-256) |
| **IS 456:2000 AMD 5** | `data/raw/amendments/is_456_2000_amendment_5.pdf` | July 2019 | Cl. 26.2.1.1 (Bond stress), Cl. 26.5.1.1 | Verified (SHA-256) |
| **IS 13920:2016 AMD 1** | `data/raw/amendments/is_13920_2016_amendment_1.pdf` | September 2017 | Cl. 5.3 couplers, Cl. 6.3.3 (2d zone), Cl. 7.6.1 | Verified (SHA-256) |
| **IS 13920:2016 AMD 2** | `data/raw/amendments/is_13920_2016_amendment_2.pdf` | December 2020 | Cl. 5.2 hooks, Cl. 6.1.1 (b>=200mm), Cl. 7.1 | Verified (SHA-256) |
| **IS 1893:2016 AMD 1** | `data/raw/amendments/is_1893_part_1_2016_amendment_1.pdf` | January 2017 | Cl. 6.4.2 Zone Z, Cl. 7.2.1 (VB), Cl. 7.6.2 (Ta) | Verified (SHA-256) |
| **IS 1893:2016 AMD 2** | `data/raw/amendments/is_1893_part_1_2016_amendment_2.pdf` | March 2020 | Table 6 (I), Table 7 (R), Cl. 7.11.1 drift | Verified (SHA-256) |
| **IS 800:2007 AMD 1** | `data/raw/amendments/is_800_2007_amendment_1.pdf` | January 2012 | Cl. 7.1.2 compression, Table 10, Table 12 | Verified (SHA-256) |
| **IS 800:2007 AMD 2** | `data/raw/amendments/is_800_2007_amendment_2.pdf` | August 2013 | Cl. 8.2.2 lateral buckling, Section 10 HSFG | Verified (SHA-256) |
| **IS 800:2007 AMD 3** | `data/raw/amendments/is_800_2007_amendment_3.pdf` | September 2015 | Table 20 edge dist, Cl. 10.5 fillet welds | Verified (SHA-256) |
| **IS 875 (P3):2015 AMD 1** | `data/raw/amendments/is_875_part_3_2015_amendment_1.pdf` | March 2016 | Cl. 6.3 wind speed, Cl. 6.3.4 cyclonic k4 | Verified (SHA-256) |

### 2.4 Official Errata Slips (2 Documents)

| Standard / Errata | Target File | Issue Date | Key Affected Clauses | Verification Status |
| :--- | :--- | :--- | :--- | :--- |
| **IS 456:2000 ERR 1** | `data/raw/errata/is_456_2000_errata_1.pdf` | December 2000 | Annex G-1.1(c) Mu,lim formula, Cl. 40.4 Vus | Verified (SHA-256) |
| **IS 800:2007 ERR 1** | `data/raw/errata/is_800_2007_errata_1.pdf` | March 2008 | Table 5 gamma_m0 factor, Section 7 | Verified (SHA-256) |

### 2.5 Supplementary Design Examples & Explanatory Commentaries (3 Documents)

| Title & Citation | Target File | Authority | Category | Verification Status |
| :--- | :--- | :--- | :--- | :--- |
| **IITK-GSDMA EQ26** | `data/raw/supplementary/iitk_gsdma_eq26_design_example.pdf` | NICEE / IIT Kanpur | Design Example (6-Storey Building) | Verified (SHA-256) |
| **IITK-GSDMA EQ06** | `data/raw/supplementary/iitk_gsdma_eq06_commentary.pdf` | NICEE / IIT Kanpur | Explanatory Commentary (Ductile Detailing) | Verified (SHA-256) |
| **SP:16 Worked Examples** | `data/raw/supplementary/sp_16_worked_design_examples.pdf` | BIS / SP:16 | Design Examples (Beams, Columns, Slabs) | Verified (SHA-256) |

---

## 3. Acquisition & Synchronization Workflow

### 3.1 Verify Entire Corpus Integrity

```bash
python src/ingestion/download_codes.py --verify-all
```
*Expected: reports 28/28 documents valid with passing %PDF- headers and exact SHA-256 checksums.*

### 3.2 Selective Download

```bash
# Acquire base standards
python src/ingestion/download_codes.py --standards

# Acquire official amendments
python src/ingestion/download_codes.py --amendments

# Acquire errata
python src/ingestion/download_codes.py --errata

# Acquire supplementary design examples & commentaries
python src/ingestion/download_codes.py --supplementary

# Or everything
python src/ingestion/download_codes.py --all
```

### 3.3 Version Control with DVC & Git LFS

Every document in `data/raw/` is tracked with Git LFS (`.gitattributes`) and has a companion `.dvc` pointer file committed to Git. The binary payload resides in `.dvc/cache` and is synchronized via:

```bash
# Track raw PDFs with DVC
dvc add data/raw/*.pdf data/raw/amendments/*.pdf data/raw/errata/*.pdf data/raw/supplementary/*.pdf

# Synchronize with remote storage
dvc push    # push to cloud remote (or local cache)
dvc pull    # restore 28 PDFs on any fresh checkout or CI runner
```
