"""
Upload Metadata-Enriched Chunks to PostgreSQL JSONB Document Store.

Step 4: Chunking & Metadata Enrichment.
Ingests multi-standard chunks into PostgreSQL document_chunks table with JSONB metadata and content.

Usage:
    python src/storage/upload_to_postgres.py --all
    python src/storage/upload_to_postgres.py --file data/processed/all_enriched_chunks.jsonl
    python src/storage/upload_to_postgres.py --file data/processed/chunks.jsonl
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.storage.postgres_db import get_store

DEFAULT_ALL_CHUNKS = Path("data/processed/all_enriched_chunks.jsonl")
LEGACY_CHUNKS = Path("data/processed/chunks.jsonl")


def upload_chunks(file_path: Path) -> int:
    """Reads JSONL chunk file and batch uploads into PostgreSQL document store."""
    if not file_path.exists():
        print(f"Error: {file_path} does not exist.")
        return 0

    print(f"Reading chunks from {file_path}...")
    chunks = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))

    print(f"Loaded {len(chunks)} chunks from {file_path.name}.")

    store = get_store()
    if not store.conn:
        print("\n[NOTE] PostgreSQL server is not connected at this time.")
        print("To run local PostgreSQL: docker compose up -d postgres")
        print("All chunks are compiled and ready in all_enriched_chunks.jsonl.")
        return len(chunks)

    print("Uploading chunks to PostgreSQL JSONB document store...")
    store.insert_chunks(chunks)
    print("Upload complete!")

    total_in_db = store.count_chunks()
    print(f"Total chunks in database: {total_in_db}")
    store.close()
    return len(chunks)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload enriched chunks to PostgreSQL JSONB document store")
    parser.add_argument("--all", action="store_true", help="Upload all 1520 enriched multi-standard chunks")
    parser.add_argument("--file", type=str, default=None, help="Custom path to chunks.jsonl file")
    args = parser.parse_args()

    target = Path(args.file) if args.file else DEFAULT_ALL_CHUNKS
    if not target.exists() and LEGACY_CHUNKS.exists():
        target = LEGACY_CHUNKS

    upload_chunks(target)
