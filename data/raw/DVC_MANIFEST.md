# DVC (Data Version Control) & Git LFS Storage Manifest

> **Scope**: Step 2: Data Acquisition & Collection  
> **Repository**: [rounaqq/is-code-rag](https://github.com/rounaqq/is-code-rag)

---

## 1. Storage Architecture Overview

To prevent Git repository bloat when storing large multi-megabyte official Indian Standard PDFs and supplementary handbooks, we implement a two-tiered version control strategy:

1. **Git LFS (Large File Storage)**:  
   Configured in [`.gitattributes`](file:///c:/Users/rouna/IS-Code-Rag/.gitattributes) for binary assets (`*.pdf`, `*.dwg`, `*.npy`). Large files are replaced with lightweight text pointer files in GitHub commits.
2. **DVC (Data Version Control)**:  
   Used for versioning data pipelines, raw standards directories, and embedding matrices across cloud environments (AWS S3, GCS, or remote file storage).

---

## 2. Standards & Handbooks Manifest

| Standard / Document | Target File | File Size (Approx) | Upstream Source | Verification Status |
| :--- | :--- | :--- | :--- | :--- |
| **IS 456:2000** | `data/raw/is_456_2000.pdf` | 13.2 MB | BIS / Public.Resource.Org | Verified (PyMuPDF) |
| **IS 13920:2016** | `data/raw/is_13920_2016.pdf` | 1.52 MB | BIS / Public.Resource.Org | Verified (PyMuPDF) |
| **IS 875 (Part 2):1987** | `data/raw/is_875_part_2_1987.pdf` | 1.48 MB | BIS / Public.Resource.Org | Verified (PyMuPDF) |
| **IS 1893 (Part 1):2016**| `data/raw/is_1893_part_1_2016.pdf` | 2.58 MB | BIS / Public.Resource.Org | Verified (PyMuPDF) |
| **IS 800:2007** | `data/raw/is_800_2007.pdf` | 5.86 MB | BIS / Public.Resource.Org | Verified (PyMuPDF) |
| **SP:16:1980** | `data/raw/sp_16_1980.pdf` | 10.4 MB | BIS / Public.Resource.Org | Verified (Design Charts) |
| **SP:34:1987** | `data/raw/sp_34_1987.pdf` | 14.8 MB | BIS / Public.Resource.Org | Verified (Detailing Handbook) |

---

## 3. How to Synchronize via DVC

```bash
# 1. Install DVC
pip install dvc

# 2. Initialize DVC in the workspace
dvc init

# 3. Track the raw standards directory
dvc add data/raw/

# 4. Configure cloud remote (e.g. S3 bucket)
dvc remote add -d s3remote s3://my-is-code-rag-storage/data/
dvc push

# 5. On a new machine / CI runner, retrieve all standards with:
dvc pull
```

All metadata, local checksums, and download endpoints are recorded in [`data/raw/registry.json`](file:///c:/Users/rouna/IS-Code-Rag/data/raw/registry.json).
