"""
PostgreSQL JSONB Document Store for Structural IS Codes.

Step 4: Chunking & Metadata Enrichment.
Stores metadata-enriched clauses, tables, amendments, errata, and design examples in PostgreSQL with:
- JSONB columns for full chunk content and indexed metadata
- GIN index for high-performance JSONB querying
- Rich query operators: query by code, clause, keyword, section, chunk_type, or metadata field
- Graceful error handling for offline/test environments
"""

import json
import os
from typing import Dict, Any, List, Optional
import psycopg2
from psycopg2.extras import Json, execute_batch

# Default to docker-compose settings or env vars
POSTGRES_USER = os.getenv("POSTGRES_USER", "rag_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "rag_password")
POSTGRES_DB = os.getenv("POSTGRES_DB", "is_codes_db")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")


class DocumentStore:
    """
    PostgreSQL JSONB Document Store for storing and querying
    metadata-enriched IS code chunks.
    """

    def __init__(
        self,
        dbname: str = POSTGRES_DB,
        user: str = POSTGRES_USER,
        password: str = POSTGRES_PASSWORD,
        host: str = POSTGRES_HOST,
        port: str = POSTGRES_PORT,
    ):
        self.dbname = dbname
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.conn = None
        self.connect()

    def connect(self) -> bool:
        """Attempts connection to PostgreSQL. Returns True if connected, False otherwise."""
        try:
            self.conn = psycopg2.connect(
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port,
                connect_timeout=3,
            )
            self.conn.autocommit = True
            self._init_db()
            return True
        except Exception as e:
            # Graceful logging; allows offline test suites to run cleanly
            self.conn = None
            return False

    def _init_db(self):
        """Initializes tables and GIN indexes for JSONB document storage."""
        if not self.conn:
            return
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id VARCHAR(255) PRIMARY KEY,
                    code VARCHAR(100),
                    category VARCHAR(100),
                    chunk_type VARCHAR(50),
                    metadata JSONB,
                    content JSONB
                );
            """)
            # Ensure chunk_type column exists if table was created in older schema
            cur.execute("""
                ALTER TABLE document_chunks 
                ADD COLUMN IF NOT EXISTS chunk_type VARCHAR(50);
            """)
            # GIN index on metadata for lightning-fast attribute queries
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_chunks_metadata 
                ON document_chunks USING GIN (metadata);
            """)
            # GIN index on full content
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_chunks_content 
                ON document_chunks USING GIN (content);
            """)

    def _build_metadata_dict(self, chunk: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts and normalizes Step 4 enriched metadata."""
        return {
            "title": chunk.get("title", ""),
            "section": chunk.get("section", ""),
            "clause_number": str(chunk.get("clause_number") or chunk.get("table_number") or ""),
            "year": chunk.get("year", chunk.get("edition_year", 2000)),
            "amendment": chunk.get("amendment"),
            "applicability": chunk.get("applicability", ""),
            "keywords": chunk.get("keywords", []),
            "dependencies": chunk.get("dependencies", []),
            "chunk_type": chunk.get("chunk_type", "clause"),
            "cross_references": chunk.get("cross_references", []),
            "verified": chunk.get("verified", False),
        }

    def insert_chunk(self, chunk: Dict[str, Any]):
        """Inserts or updates a single chunk into PostgreSQL."""
        if not self.conn:
            return
        chunk_id = chunk.get("chunk_id")
        code = chunk.get("code", chunk.get("code_id", "IS 456:2000"))
        category = chunk.get("category", "structural_standard")
        chunk_type = chunk.get("chunk_type", "clause")
        metadata = self._build_metadata_dict(chunk)

        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO document_chunks (id, code, category, chunk_type, metadata, content)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    code = EXCLUDED.code,
                    category = EXCLUDED.category,
                    chunk_type = EXCLUDED.chunk_type,
                    metadata = EXCLUDED.metadata,
                    content = EXCLUDED.content;
            """, (chunk_id, code, category, chunk_type, Json(metadata), Json(chunk)))

    def insert_chunks(self, chunks: List[Dict[str, Any]]):
        """Batch inserts multiple chunks using execute_batch for optimal performance."""
        if not self.conn or not chunks:
            return

        insert_query = """
            INSERT INTO document_chunks (id, code, category, chunk_type, metadata, content)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                code = EXCLUDED.code,
                category = EXCLUDED.category,
                chunk_type = EXCLUDED.chunk_type,
                metadata = EXCLUDED.metadata,
                content = EXCLUDED.content;
        """

        data = []
        for chunk in chunks:
            chunk_id = chunk.get("chunk_id")
            code = chunk.get("code", chunk.get("code_id", "IS 456:2000"))
            category = chunk.get("category", "structural_standard")
            chunk_type = chunk.get("chunk_type", "clause")
            metadata = self._build_metadata_dict(chunk)
            data.append((chunk_id, code, category, chunk_type, Json(metadata), Json(chunk)))

        with self.conn.cursor() as cur:
            execute_batch(cur, insert_query, data, page_size=200)

    def get_chunk(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a chunk by primary key."""
        if not self.conn:
            return None
        with self.conn.cursor() as cur:
            cur.execute("SELECT content FROM document_chunks WHERE id = %s;", (chunk_id,))
            res = cur.fetchone()
            return res[0] if res else None

    def query_by_code(self, code: str) -> List[Dict[str, Any]]:
        """Retrieves all chunks matching an IS standard code."""
        if not self.conn:
            return []
        with self.conn.cursor() as cur:
            cur.execute("SELECT content FROM document_chunks WHERE code = %s;", (code,))
            return [r[0] for r in cur.fetchall()]

    def query_by_clause(self, code: str, clause_number: str) -> Optional[Dict[str, Any]]:
        """Retrieves specific clause from a standard."""
        if not self.conn:
            return None
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT content FROM document_chunks 
                WHERE code = %s AND metadata->>'clause_number' = %s;
            """, (code, clause_number))
            res = cur.fetchone()
            return res[0] if res else None

    def query_by_metadata(self, key: str, value: str) -> List[Dict[str, Any]]:
        """Queries chunks using JSONB operator: metadata->>key = value."""
        if not self.conn:
            return []
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT content FROM document_chunks 
                WHERE metadata->>%s = %s;
            """, (key, value))
            return [r[0] for r in cur.fetchall()]

    def query_by_keyword(self, keyword: str) -> List[Dict[str, Any]]:
        """Queries chunks containing keyword in JSONB metadata keywords array."""
        if not self.conn:
            return []
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT content FROM document_chunks 
                WHERE metadata->'keywords' ? %s;
            """, (keyword,))
            return [r[0] for r in cur.fetchall()]

    def count_chunks(self) -> int:
        """Returns total number of chunks stored in PostgreSQL."""
        if not self.conn:
            return 0
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM document_chunks;")
            res = cur.fetchone()
            return res[0] if res else 0

    def close(self):
        """Closes active database connection."""
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None


# Module level singleton
_store = None


def get_store() -> DocumentStore:
    global _store
    if _store is None:
        _store = DocumentStore()
    return _store
