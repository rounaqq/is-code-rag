"""
IS Code & Supplementary Handbook Acquisition Script.

Step 2: Data Acquisition & Collection.
Downloads official Indian Standard PDFs, amendments, and supplementary handbooks from public repositories,
validates PDF headers, computes SHA-256 checksums, and updates the data registry.

Usage:
    python src/ingestion/download_codes.py --all
    python src/ingestion/download_codes.py --code "IS 13920:2016"
"""

import argparse
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path
from typing import Dict, Any, Optional


REGISTRY_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "registry.json"
DATA_RAW_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw"


def compute_sha256(filepath: Path) -> str:
    """Computes the SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def validate_pdf_file(filepath: Path) -> bool:
    """Verifies that file exists, has size > 1000 bytes, and starts with %PDF header."""
    if not filepath.exists() or filepath.stat().st_size < 1000:
        return False
    with open(filepath, "rb") as f:
        header = f.read(8)
    return header.startswith(b"%PDF-")


def download_file(url: str, dest_path: Path, max_retries: int = 3, timeout_sec: int = 30) -> bool:
    """
    Downloads file from URL with user-agent headers, progress indication, and retries.
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = dest_path.with_suffix(".tmp")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    req = urllib.request.Request(url, headers=headers)

    for attempt in range(1, max_retries + 1):
        try:
            print(f"  --> Connecting to {url} (attempt {attempt}/{max_retries})...")
            with urllib.request.urlopen(req, timeout=timeout_sec) as response, open(temp_path, "wb") as out_file:
                content_len = response.headers.get("Content-Length")
                total_size = int(content_len) if content_len else None
                bytes_downloaded = 0
                block_size = 65536

                while True:
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    bytes_downloaded += len(buffer)
                    out_file.write(buffer)
                    if total_size:
                        pct = (bytes_downloaded / total_size) * 100.0
                        sys.stdout.write(f"\r      Downloaded: {bytes_downloaded / (1024*1024):.2f} MB / {total_size / (1024*1024):.2f} MB ({pct:.1f}%)")
                    else:
                        sys.stdout.write(f"\r      Downloaded: {bytes_downloaded / (1024*1024):.2f} MB")
                    sys.stdout.flush()

                print()

            if validate_pdf_file(temp_path):
                temp_path.replace(dest_path)
                print(f"  [SUCCESS] Saved to {dest_path.name} ({dest_path.stat().st_size / (1024*1024):.2f} MB)")
                return True
            else:
                print(f"  [ERROR] Downloaded file failed PDF validation.")
                if temp_path.exists():
                    temp_path.unlink()
        except Exception as e:
            print(f"  [WARN] Download error: {e}")
            if temp_path.exists():
                temp_path.unlink()
            time.sleep(2)

    return False


def run_acquisition(target_code: Optional[str] = None, download_all: bool = False) -> Dict[str, Any]:
    """
    Executes acquisition for specified code or all pending items in registry.
    """
    if not REGISTRY_FILE.exists():
        raise FileNotFoundError(f"Registry file not found at {REGISTRY_FILE}")

    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        registry = json.load(f)

    all_items = registry.get("standards", []) + registry.get("handbooks", [])
    results = {"downloaded": 0, "failed": 0, "already_present": 0}

    for item in all_items:
        code = item.get("code")
        filename = item.get("filename")
        archive_url = item.get("archive_url")

        if not filename or not archive_url:
            continue

        if target_code and target_code.lower() not in code.lower():
            continue

        dest_file = DATA_RAW_DIR / filename
        print(f"\nProcessing: {code} - {item.get('title')}")

        if dest_file.exists() and validate_pdf_file(dest_file):
            print(f"  [EXISTS] File already exists and is valid: {dest_file.name}")
            sha256 = compute_sha256(dest_file)
            item["status"] = "acquired"
            item["file_size_bytes"] = dest_file.stat().st_size
            item["sha256"] = sha256
            results["already_present"] += 1
            continue

        if download_all or target_code:
            success = download_file(archive_url, dest_file)
            if success:
                sha256 = compute_sha256(dest_file)
                item["status"] = "acquired"
                item["file_size_bytes"] = dest_file.stat().st_size
                item["sha256"] = sha256
                results["downloaded"] += 1
            else:
                results["failed"] += 1
        else:
            print(f"  [QUEUED] URL available: {archive_url}")

    # Save updated registry
    with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)

    print(f"\nAcquisition Summary: {results['downloaded']} downloaded, {results['already_present']} already present, {results['failed']} failed.")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Acquire official IS Code PDFs and Handbooks")
    parser.add_argument("--all", action="store_true", help="Download all pending standards and handbooks")
    parser.add_argument("--code", type=str, help="Specific code to download (e.g., 'IS 13920')")
    args = parser.parse_args()

    run_acquisition(target_code=args.code, download_all=args.all)
