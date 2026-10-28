import json
from pathlib import Path
import sys

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.storage.postgres_db import get_store

CHUNKS_PATH = Path("data/processed/chunks.jsonl")

def upload_chunks_to_postgres():
    if not CHUNKS_PATH.exists():
        print(f"Error: {CHUNKS_PATH} does not exist.")
        sys.exit(1)
        
    print(f"Reading chunks from {CHUNKS_PATH}...")
    chunks = []
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
                
    print(f"Loaded {len(chunks)} chunks from file.")
    
    store = get_store()
    if not store.conn:
        print("Failed to connect to PostgreSQL. Is the database running?")
        sys.exit(1)
        
    print("Uploading chunks to PostgreSQL JSONB document store...")
    
    # Batch insert in smaller chunks if needed, but 1000 is fine for one execute_batch
    store.insert_chunks(chunks)
    
    print("Upload complete!")
    
    # Verify a little bit
    print("\nVerifying data in PostgreSQL...")
    with store.conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM document_chunks;")
        count = cur.fetchone()[0]
        print(f"Total chunks in database: {count}")
        
    store.close()

if __name__ == "__main__":
    upload_chunks_to_postgres()
