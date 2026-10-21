"""
FastAPI application for IS 456 Structural Retrieval RAG.
Provides health monitoring, authenticated query retrieval, audit logging, and safe error handling.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.retrieval.pipeline import retrieve

# Load environment variables from .env if present
load_dotenv()

AUDIT_LOG_FILE = Path("data/audit/audit.jsonl")


def get_api_keys() -> Dict[str, str]:
    """
    Parses authorized API keys from environment variable IS_RAG_API_KEYS.
    Format: comma-separated 'name:key' pairs.
    Returns: mapping of key -> name.
    """
    raw_keys = os.getenv("IS_RAG_API_KEYS", "")
    key_map = {}
    for item in raw_keys.split(","):
        item = item.strip()
        if ":" in item:
            name, key = item.split(":", 1)
            name = name.strip()
            key = key.strip()
            if name and key:
                key_map[key] = name
    return key_map


def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> str:
    """
    Validates X-API-Key header.
    Returns key_name on success.
    Returns 401 without revealing validation details on failure.
    """
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    key_map = get_api_keys()
    key_name = key_map.get(x_api_key.strip())
    if not key_name:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    return key_name


def log_audit_event(
    key_name: str,
    query: str,
    k: int,
    returned_chunk_ids: List[str],
    rerank_scores: List[float],
    latency_ms: float,
    status_code: int,
) -> None:
    """
    Safely logs retrieval requests to data/audit/audit.jsonl.
    Never logs the secret API key itself.
    """
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "key_name": key_name,
        "query": query,
        "k": k,
        "returned_chunk_ids": returned_chunk_ids,
        "rerank_scores": rerank_scores,
        "latency_ms": latency_ms,
        "status_code": status_code,
    }
    try:
        AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"WARNING: Audit logging failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Preloads retrieval models and chunk data once at application startup.
    """
    print("Preloading retrieval models and chunk index during lifespan startup...")
    # Trigger model singletons loading
    retrieve("warmup structural query", k=1)
    print("Retrieval models preloaded successfully.")
    yield


app = FastAPI(
    title="IS 456 Structural Retrieval API",
    description="Deterministic clause and table retrieval over IS 456:2000 for structural RC beam design.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Prevents leakage of internal file paths or stack traces on unhandled exceptions.
    """
    print(f"Internal server error handling {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500, description="Structural query string (3 to 500 characters)")
    k: int = Field(default=3, ge=1, le=5, description="Number of chunks to return (default 3, max 5)")


class QueryResponse(BaseModel):
    query: str
    results: List[Dict[str, Any]]
    note: str = "ranking scores are not probabilities"


@app.get("/health")
def health_check():
    """Health check endpoint requiring no API key."""
    return {"status": "ok"}


@app.post("/v1/rag/query", response_model=QueryResponse)
def query_rag(req: QueryRequest, key_name: str = Depends(verify_api_key)):
    """
    Authenticated structural query endpoint.
    Retrieves top-k relevant clauses/tables with cross-encoder reranking.
    """
    start_time = time.perf_counter()
    results = retrieve(req.query, k=req.k)
    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

    chunk_ids = [r["chunk_id"] for r in results]
    scores = [r["rerank_score"] for r in results]

    # Audit logging
    log_audit_event(
        key_name=key_name,
        query=req.query,
        k=req.k,
        returned_chunk_ids=chunk_ids,
        rerank_scores=scores,
        latency_ms=latency_ms,
        status_code=200,
    )

    return QueryResponse(
        query=req.query,
        results=results,
        note="ranking scores are not probabilities",
    )
