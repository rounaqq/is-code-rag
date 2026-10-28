import json
import os
import psycopg2
from psycopg2.extras import Json
from typing import Dict, Any, List, Optional

# Default to the docker-compose settings if not in env
POSTGRES_USER = os.getenv("POSTGRES_USER", "rag_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "rag_password")
POSTGRES_DB = os.getenv("POSTGRES_DB", "is_codes_db")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

class DocumentStore:
    def __init__(self):
        self.conn = None
        self.connect()

    def connect(self):
        try:
            self.conn = psycopg2.connect(
                dbname=POSTGRES_DB,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
                host=POSTGRES_HOST,
                port=POSTGRES_PORT
            )
            self.conn.autocommit = True
            self._init_db()
        except Exception as e:
            print(f"Error connecting to PostgreSQL: {e}")

    def _init_db(self):
        """Initialize the table with JSONB column for document storage."""
        if not self.conn:
            return
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id VARCHAR(255) PRIMARY KEY,
                    code VARCHAR(100),
                    category VARCHAR(100),
                    metadata JSONB,
                    content JSONB
                );
            """)
            # Create GIN index for faster JSONB querying
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_chunks_metadata 
                ON document_chunks USING GIN (metadata);
            """)

    def insert_chunk(self, chunk: Dict[str, Any]):
        """Insert a single chunk into the document store."""
        if not self.conn:
            return
        chunk_id = chunk.get("chunk_id")
        code = chunk.get("code")
        category = chunk.get("category")
        
        # We can store the full chunk in content, and specific metadata in metadata
        metadata = {
            "title": chunk.get("title"),
            "section": chunk.get("section"),
            "applicability": chunk.get("applicability"),
            "keywords": chunk.get("keywords", [])
        }
        
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO document_chunks (id, code, category, metadata, content)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    code = EXCLUDED.code,
                    category = EXCLUDED.category,
                    metadata = EXCLUDED.metadata,
                    content = EXCLUDED.content;
            """, (chunk_id, code, category, Json(metadata), Json(chunk)))

    def insert_chunks(self, chunks: List[Dict[str, Any]]):
        """Insert multiple chunks into the document store."""
        if not self.conn:
            return
        
        # Using execute_batch for better performance
        from psycopg2.extras import execute_batch
        
        insert_query = """
            INSERT INTO document_chunks (id, code, category, metadata, content)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                code = EXCLUDED.code,
                category = EXCLUDED.category,
                metadata = EXCLUDED.metadata,
                content = EXCLUDED.content;
        """
        
        data = []
        for chunk in chunks:
            chunk_id = chunk.get("chunk_id")
            code = chunk.get("code")
            category = chunk.get("category")
            metadata = {
                "title": chunk.get("title"),
                "section": chunk.get("section"),
                "applicability": chunk.get("applicability"),
                "keywords": chunk.get("keywords", [])
            }
            data.append((chunk_id, code, category, Json(metadata), Json(chunk)))
            
        with self.conn.cursor() as cur:
            execute_batch(cur, insert_query, data)

    def get_chunk(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a chunk by its ID."""
        if not self.conn:
            return None
            
        with self.conn.cursor() as cur:
            cur.execute("SELECT content FROM document_chunks WHERE id = %s;", (chunk_id,))
            result = cur.fetchone()
            if result:
                return result[0]
        return None

    def query_by_metadata(self, key: str, value: str) -> List[Dict[str, Any]]:
        """Example query using JSONB operators."""
        if not self.conn:
            return []
            
        with self.conn.cursor() as cur:
            # Query where metadata->>key = value
            cur.execute("""
                SELECT content FROM document_chunks 
                WHERE metadata->>%s = %s;
            """, (key, value))
            results = cur.fetchall()
            return [res[0] for res in results]

    def close(self):
        if self.conn:
            self.conn.close()

# Module level singleton
_store = None

def get_store() -> DocumentStore:
    global _store
    if _store is None:
        _store = DocumentStore()
    return _store
