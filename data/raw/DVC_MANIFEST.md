# DVC (Data Version Control) & Git LFS Storage Manifest

> **Scope**: Step 2: Data Acquisition & Collection  
> **Repository**: [rounaqq/is-code-rag](https://github.com/rounaqq/is-code-rag)

---

## 1. Storage Architecture Overview

To prevent Git repository bloat when storing large multi-megabyte official Indian Standard PDFs and supplementary handbooks, we implement a two-tiered version control strategy:

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
| Tracked artifacts | 10 PDFs (~90.9 MB) via `data/raw/*.pdf.dvc` |

> **Production remote**: for cloud/CI deployments, point the remote at object storage instead of the local directory:
> ```bash
> dvc remote add -d storageremote s3://my-is-code-rag-storage/data/ && dvc push
> ```

---

## 2. Standards & Handbooks Manifest

All documents are acquired from public mirrors (Public.Resource.Org via the Internet Archive), validated as `%PDF-` files, and recorded with SHA-256 checksums in [`data/raw/registry.json`](file:///c:/Users/rouna/IS-Code-Rag/data/raw/registry.json).

| Standard / Document | Target File | File Size | Upstream Source | Verification Status |
| :--- | :--- | :--- | :--- | :--- |
| **IS 456:2000** | `data/raw/is_456_2000.pdf` | 7.10 MB | BIS / Public.Resource.Org | Verified (SHA-256) |
| **IS 13920:2016** | `data/raw/is_13920_2016.pdf` | 1.52 MB | BIS / Public.Resource.Org | Verified (SHA-256) |
| **IS 875 (Part 1):1987** | `data/raw/is_875_part_1_1987.pdf` | 1.78 MB | BIS / Public.Resource.Org | Verified (SHA-256) |
| **IS 875 (Part 2):1987** | `data/raw/is_875_part_2_1987.pdf` | 1.05 MB | BIS / Public.Resource.Org | Verified (SHA-256) |
| **IS 875 (Part 3):2015** | `data/raw/is_875_part_3_2015.pdf` | 9.12 MB | BIS / Public.Resource.Org | Verified (SHA-256) |
| **IS 1893 (Part 1):2016** | `data/raw/is_1893_part_1_2016.pdf` | 4.32 MB | BIS / Public.Resource.Org | Verified (SHA-256) |
| **IS 800:2007** | `data/raw/is_800_2007.pdf` | 10.85 MB | BIS / Public.Resource.Org | Verified (SHA-256) |
| **SP:16:1980** | `data/raw/sp_16_1980.pdf` | 26.42 MB | BIS / Public.Resource.Org | Verified (Design Charts) |
| **SP:34:1987** | `data/raw/sp_34_1987.pdf` | 16.38 MB | BIS / Public.Resource.Org | Verified (Detailing Handbook) |
| **SP:24:1983** | `data/raw/sp_24_1983.pdf` | 12.31 MB | BIS / Public.Resource.Org | Verified (Explanatory Handbook) |

---

## 3. Acquisition & Synchronization Workflow

### 3.1 Acquire the raw PDFs (SHA-256 validated)

```bash
# Download every pending standard/handbook and refresh the registry checksums
python src/ingestion/download_codes.py --all

# Or a single document
python src/ingestion/download_codes.py --code "IS 875 (Part 1)"
```

### 3.2 Version the raw governed data with DVC

```bash
# 1. Install DVC
pip install dvc

# 2. (Already done in this repo — run only on a fresh clone)
dvc init

# 3. Track each acquired standard PDF
dvc add data/raw/is_456_2000.pdf data/raw/is_13920_2016.pdf \
        data/raw/is_875_part_1_1987.pdf data/raw/is_875_part_2_1987.pdf \
        data/raw/is_875_part_3_2015.pdf data/raw/is_1893_part_1_2016.pdf \
        data/raw/is_800_2007.pdf data/raw/sp_16_1980.pdf \
        data/raw/sp_34_1987.pdf data/raw/sp_24_1983.pdf

# 4. Configure the remote (local directory by default; S3/GCS for cloud)
dvc remote add -d localremote ../data/dvc_remote
dvc push
```

### 3.3 Retrieve the data on a new machine / CI runner

```bash
dvc pull      # restores every data/raw/*.pdf from the configured remote
```

All metadata, local checksums, and download endpoints are recorded in [`data/raw/registry.json`](file:///c:/Users/rouna/IS-Code-Rag/data/raw/registry.json).
