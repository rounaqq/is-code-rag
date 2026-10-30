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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse
from pydantic import BaseModel, Field

from src.retrieval.pipeline import retrieve
from src.retrieval.multicode_search import retrieve_multicode
from src.generation.design_assistant import design_beam_assistant, BASE_DISCLAIMER
from src.generation.beam_sizing import size_beam_from_loads
from src.generation.column_sizing import size_column_from_load
from src.generation.slab_sizing import size_slab_from_loads
from src.generation.footing_sizing import size_footing_from_load
from src.cad.beam_dxf import export_dxf_from_design
from src.cad.column_dxf import export_column_dxf
from src.cad.slab_dxf import export_slab_dxf
from src.cad.footing_dxf import export_footing_dxf
from src.cad.engineer_review import (
    generate_review_report,
    apply_engineer_overrides,
    sign_off_design,
)
from src.validation.seismic_compliance import (
    resolve_beam_seismic_conflicts,
    resolve_column_seismic_conflicts,
)
from src.generation.seismic_base_shear import calculate_seismic_base_shear

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

    token = x_api_key.strip()
    if ":" in token:
        token = token.split(":")[-1].strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    key_map = get_api_keys()
    key_name = key_map.get(token)
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

# Enable CORS for React + Vite development server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.get("/", include_in_schema=False)
def root_redirect():
    """Redirects base URL directly to interactive Swagger API documentation."""
    return RedirectResponse(url="/docs")


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


class DesignAssistantRequest(BaseModel):
    query: Optional[str] = Field(None, description="Natural language prompt from structural engineer")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Direct structural parameters (span_m, dead_load_kN_per_m, etc.)")
    max_aggregate_size_mm: Optional[float] = Field(20.0, description="Nominal maximum aggregate size in mm per IS 456 Cl. 26.3.2 (default 20.0)")


@app.post("/v1/design/assistant")
def design_assistant_endpoint(req: DesignAssistantRequest, key_name: str = Depends(verify_api_key)):
    """
    Authenticated IS 456 Structural Design Assistant endpoint.
    Extracts parameters, executes deterministic sizing, and explains results with clause citations.
    """
    start_time = time.perf_counter()
    user_input = req.parameters if req.parameters is not None else req.query
    if user_input is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either 'query' or 'parameters' must be provided.",
        )

    if isinstance(user_input, dict) and req.max_aggregate_size_mm is not None:
        if "max_aggregate_size_mm" not in user_input:
            user_input["max_aggregate_size_mm"] = req.max_aggregate_size_mm

    result = design_beam_assistant(user_input=user_input)
    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

    log_audit_event(
        key_name=key_name,
        query=str(req.query or req.parameters),
        k=0,
        returned_chunk_ids=[],
        rerank_scores=[],
        latency_ms=latency_ms,
        status_code=200,
    )

    return result


class DesignReviewRequest(BaseModel):
    span_m: Optional[float] = Field(None, description="Clear span in meters")
    dead_load_kN_per_m: Optional[float] = Field(None, description="Dead load in kN/m excluding self weight")
    live_load_kN_per_m: Optional[float] = Field(None, description="Live load in kN/m")
    fck: Optional[float] = Field(25.0, description="Concrete characteristic compressive strength in N/mm2")
    fy: Optional[float] = Field(500.0, description="Steel characteristic yield strength in N/mm2")
    exposure: Optional[str] = Field("Moderate", description="Environmental exposure condition")
    max_aggregate_size_mm: Optional[float] = Field(20.0, description="Nominal maximum aggregate size in mm")
    design: Optional[Dict[str, Any]] = Field(None, description="Existing design dictionary to review")
    overrides: Optional[Dict[str, Any]] = Field(None, description="Optional engineer overrides to apply")
    reviewer_name: Optional[str] = Field(None, description="Reviewer name (e.g. Er. Sharma)")
    reviewer_role: Optional[str] = Field(None, description="Reviewer role (e.g. Senior Structural Engineer)")
    review_date: Optional[str] = Field(None, description="Review date (e.g. 2026-10-24)")
    outcome: Optional[str] = Field(None, description="Review outcome (e.g. Reviewed)")
    sign_off_engineer: Optional[str] = Field(None, description="Alias for reviewer_name")
    remarks: Optional[str] = Field(None, description="Engineer review remarks")


@app.post("/v1/design/review")
def design_review_endpoint(req: DesignReviewRequest, key_name: str = Depends(verify_api_key)):
    """
    Step 8 Engineer Review & Feedback Loop endpoint.
    Generates a structured review sheet, applies engineer overrides, and records formal review.
    """
    start_time = time.perf_counter()

    current_design: Optional[Dict[str, Any]] = None
    sizing_res: Optional[Dict[str, Any]] = None

    if req.design is not None:
        current_design = dict(req.design)
    elif req.span_m is not None and req.dead_load_kN_per_m is not None and req.live_load_kN_per_m is not None:
        sizing_res = size_beam_from_loads(
            span_m=req.span_m,
            dead_load_kN_per_m=req.dead_load_kN_per_m,
            live_load_kN_per_m=req.live_load_kN_per_m,
            fck=req.fck or 25.0,
            fy=req.fy or 500.0,
            exposure=req.exposure or "Moderate",
            max_aggregate_size_mm=req.max_aggregate_size_mm or 20.0,
        )
        if sizing_res.get("status") == "needs_review":
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            log_audit_event(
                key_name=key_name,
                query=f"design_review span={req.span_m}",
                k=0,
                returned_chunk_ids=[],
                rerank_scores=[],
                latency_ms=latency_ms,
                status_code=200,
            )
            return sizing_res
        current_design = sizing_res["design_dict"]
        current_design["span_m"] = req.span_m
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either 'design' dictionary or (span_m, dead_load_kN_per_m, live_load_kN_per_m) must be provided.",
        )

    # Apply engineer overrides if requested
    if req.overrides:
        override_res = apply_engineer_overrides(current_design, req.overrides)
        if override_res["status"] == "override_rejected":
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            log_audit_event(
                key_name=key_name,
                query="design_review override_rejected",
                k=0,
                returned_chunk_ids=[],
                rerank_scores=[],
                latency_ms=latency_ms,
                status_code=400,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "Engineer overrides violate IS 456 rules", "reasons": override_res["reasons"]},
            )
        current_design = override_res["design"]

    # Apply review status only when reviewer name, role, and date are provided
    r_name = req.reviewer_name or req.sign_off_engineer
    if r_name and req.reviewer_role and req.review_date:
        current_design = sign_off_design(
            design=current_design,
            reviewer_name=r_name,
            reviewer_role=req.reviewer_role,
            review_date=req.review_date,
            outcome=req.outcome or "Reviewed",
            remarks=req.remarks,
        )
    elif r_name:
        current_design["reviewer_name"] = r_name
        current_design["engineer_remarks"] = req.remarks or ""

    # Generate full report
    review_report = generate_review_report(current_design)
    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

    log_audit_event(
        key_name=key_name,
        query=f"design_review status={review_report['approval_status']}",
        k=0,
        returned_chunk_ids=[],
        rerank_scores=[],
        latency_ms=latency_ms,
        status_code=200,
    )

    return {
        "status": "success",
        "design": current_design,
        "design_dict": current_design,
        "review_report": review_report,
    }


class DesignDxfRequest(BaseModel):
    design: Optional[Dict[str, Any]] = Field(None, description="Validated design dictionary to export")
    span_m: Optional[float] = Field(None, description="Clear span in meters")
    dead_load_kN_per_m: Optional[float] = Field(None, description="Dead load in kN/m excluding self weight")
    live_load_kN_per_m: Optional[float] = Field(None, description="Live load in kN/m")
    fck: Optional[float] = Field(25.0, description="Concrete characteristic compressive strength in N/mm2")
    fy: Optional[float] = Field(500.0, description="Steel characteristic yield strength in N/mm2")
    exposure: Optional[str] = Field("Moderate", description="Environmental exposure condition")
    max_aggregate_size_mm: Optional[float] = Field(20.0, description="Nominal maximum aggregate size in mm")
    reviewer_name: Optional[str] = Field(None, description="Reviewer name (e.g. Er. Sharma)")
    reviewer_role: Optional[str] = Field(None, description="Reviewer role (e.g. Senior Structural Engineer)")
    review_date: Optional[str] = Field(None, description="Review date (e.g. 2026-10-24)")
    outcome: Optional[str] = Field(None, description="Review outcome (e.g. Reviewed)")
    sign_off_engineer: Optional[str] = Field(None, description="Alias for reviewer_name")
    remarks: Optional[str] = Field(None, description="Optional engineer remarks for title block")
    output_filename: Optional[str] = Field("beam_design.dxf", description="Output DXF filename")


@app.post("/v1/design/dxf")
def design_dxf_endpoint(req: DesignDxfRequest, key_name: str = Depends(verify_api_key)):
    """
    Step 8 2D CAD DXF Drawing Export endpoint.
    Takes validated parameters or sizing loads, generates a 2D DXF drawing with IS 456 annotations,
    and returns export metadata.
    """
    start_time = time.perf_counter()

    design: Optional[Dict[str, Any]] = None

    if req.design is not None:
        design = dict(req.design)
    elif req.span_m is not None and req.dead_load_kN_per_m is not None and req.live_load_kN_per_m is not None:
        sizing_res = size_beam_from_loads(
            span_m=req.span_m,
            dead_load_kN_per_m=req.dead_load_kN_per_m,
            live_load_kN_per_m=req.live_load_kN_per_m,
            fck=req.fck or 25.0,
            fy=req.fy or 500.0,
            exposure=req.exposure or "Moderate",
            max_aggregate_size_mm=req.max_aggregate_size_mm or 20.0,
        )
        if sizing_res.get("status") == "needs_review":
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            log_audit_event(
                key_name=key_name,
                query=f"design_dxf needs_review span={req.span_m}",
                k=0,
                returned_chunk_ids=[],
                rerank_scores=[],
                latency_ms=latency_ms,
                status_code=200,
            )
            return {
                "status": "needs_review",
                "reason": sizing_res.get("reason"),
                "dxf_path": None,
                "sizing": sizing_res,
            }
        design = sizing_res["design_dict"]
        design["span_m"] = req.span_m
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either 'design' dictionary or (span_m, dead_load_kN_per_m, live_load_kN_per_m) must be provided.",
        )

    # Apply engineer review if reviewer_name, reviewer_role, and review_date are supplied
    r_name = req.reviewer_name or req.sign_off_engineer
    if r_name and req.reviewer_role and req.review_date:
        design = sign_off_design(
            design=design,
            reviewer_name=r_name,
            reviewer_role=req.reviewer_role,
            review_date=req.review_date,
            outcome=req.outcome or "Reviewed",
            remarks=req.remarks,
        )

    cad_dir = Path("data/processed/cad")
    cad_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(req.output_filename or "beam_design.dxf").name
    out_path = cad_dir / filename

    dxf_result = export_dxf_from_design(
        design=design,
        output_path=str(out_path),
        validate_first=True,
    )

    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
    log_audit_event(
        key_name=key_name,
        query=f"design_dxf output={filename}",
        k=0,
        returned_chunk_ids=[],
        rerank_scores=[],
        latency_ms=latency_ms,
        status_code=200,
    )

    return {
        "status": dxf_result["status"],
        "dxf_path": dxf_result.get("dxf_path"),
        "reviewer_name": design.get("reviewer_name"),
        "review_date": design.get("review_date"),
        "outcome": design.get("outcome"),
        "is456_citations": dxf_result.get("is456_citations"),
        "validation": dxf_result.get("validation"),
    }


class ColumnReviewRequest(BaseModel):
    axial_load_kN: float = Field(..., gt=0, description="Service axial load in kN (unfactored)")
    length_m: Optional[float] = Field(3.0, gt=0, description="Unsupported column length in meters (default 3.0)")
    b_mm: Optional[float] = Field(None, gt=0, description="Column width in mm (optional, auto-sized if null)")
    D_mm: Optional[float] = Field(None, gt=0, description="Column depth in mm (optional, auto-sized if null)")
    fck: Optional[float] = Field(25.0, description="Concrete compressive strength in N/mm2 (default 25.0)")
    fy: Optional[float] = Field(500.0, description="Steel yield strength in N/mm2 (default 500.0)")
    exposure: Optional[str] = Field("Moderate", description="Environmental exposure condition (default Moderate)")


@app.post("/v1/design/column/review")
def design_column_review_endpoint(req: ColumnReviewRequest, key_name: str = Depends(verify_api_key)):
    """
    Pillar 1: IS 456 RC Column Design & Sizing endpoint.
    Computes short axial columns with minimum eccentricity, rebar selection, and lateral ties.
    """
    start_time = time.perf_counter()
    sizing_res = size_column_from_load(
        axial_load_kN=req.axial_load_kN,
        length_m=req.length_m or 3.0,
        b_mm=req.b_mm,
        D_mm=req.D_mm,
        fck=req.fck or 25.0,
        fy=req.fy or 500.0,
        exposure=req.exposure or "Moderate",
    )
    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
    log_audit_event(
        key_name=key_name,
        query=f"design_column_review axial={req.axial_load_kN}kN",
        k=0,
        returned_chunk_ids=[],
        rerank_scores=[],
        latency_ms=latency_ms,
        status_code=200,
    )
    return sizing_res


class ColumnDxfRequest(BaseModel):
    axial_load_kN: float = Field(..., gt=0, description="Service axial load in kN")
    length_m: Optional[float] = Field(3.0, gt=0, description="Unsupported column length in meters")
    b_mm: Optional[float] = Field(None, gt=0, description="Column width in mm")
    D_mm: Optional[float] = Field(None, gt=0, description="Column depth in mm")
    fck: Optional[float] = Field(25.0, description="Concrete compressive strength in N/mm2")
    fy: Optional[float] = Field(500.0, description="Steel yield strength in N/mm2")
    exposure: Optional[str] = Field("Moderate", description="Environmental exposure condition")
    output_filename: Optional[str] = Field("column_design.dxf", description="Output DXF filename")


@app.post("/v1/design/column/dxf")
def design_column_dxf_endpoint(req: ColumnDxfRequest, key_name: str = Depends(verify_api_key)):
    """
    Pillar 1: IS 456 RC Column 2D CAD DXF Export endpoint.
    Computes column design, generates 2D AutoCAD blueprint with cross-section, elevation, and ties.
    """
    start_time = time.perf_counter()
    sizing_res = size_column_from_load(
        axial_load_kN=req.axial_load_kN,
        length_m=req.length_m or 3.0,
        b_mm=req.b_mm,
        D_mm=req.D_mm,
        fck=req.fck or 25.0,
        fy=req.fy or 500.0,
        exposure=req.exposure or "Moderate",
    )
    if sizing_res.get("status") == "needs_review":
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        log_audit_event(
            key_name=key_name,
            query=f"design_column_dxf needs_review axial={req.axial_load_kN}kN",
            k=0,
            returned_chunk_ids=[],
            rerank_scores=[],
            latency_ms=latency_ms,
            status_code=200,
        )
        return sizing_res

    cad_dir = Path("data/processed/cad")
    cad_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(req.output_filename or "column_design.dxf").name
    out_path = cad_dir / filename

    dxf_result = export_column_dxf(
        design=sizing_res["design_dict"],
        output_path=str(out_path),
    )
    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
    log_audit_event(
        key_name=key_name,
        query=f"design_column_dxf output={filename}",
        k=0,
        returned_chunk_ids=[],
        rerank_scores=[],
        latency_ms=latency_ms,
        status_code=200,
    )
    return {
        "status": dxf_result["status"],
        "dxf_path": dxf_result["dxf_path"],
        "section_dimensions": dxf_result["section_dimensions"],
        "rebar": dxf_result["rebar"],
        "ties": dxf_result["ties"],
        "approval_status": dxf_result["approval_status"],
    }


class SlabReviewRequest(BaseModel):
    lx_m: float = Field(..., gt=0, description="Shorter slab span in meters")
    ly_m: float = Field(..., gt=0, description="Longer slab span in meters")
    live_load_kN_m2: float = Field(..., gt=0, description="Service live/imposed load in kN/m2")
    floor_finish_kN_m2: Optional[float] = Field(1.0, ge=0, description="Floor finish load in kN/m2 (default 1.0)")
    support_width_mm: Optional[float] = Field(230.0, gt=0, description="Width of supporting wall/beam in mm (default 230.0)")
    fck: Optional[float] = Field(25.0, description="Concrete compressive strength in N/mm2 (default 25.0)")
    fy: Optional[float] = Field(500.0, description="Steel yield strength in N/mm2 (default 500.0)")
    exposure: Optional[str] = Field("Moderate", description="Environmental exposure condition (default Moderate)")
    support_condition: Optional[str] = Field("simply_supported", description="Support condition: simply_supported or continuous")


@app.post("/v1/design/slab/review")
def design_slab_review_endpoint(req: SlabReviewRequest, key_name: str = Depends(verify_api_key)):
    """
    Pillar 1: IS 456 RC Slab Design & Sizing endpoint.
    Computes one-way or two-way slab thickness, deflection limits, flexural steel, and spacing checks.
    """
    start_time = time.perf_counter()
    sizing_res = size_slab_from_loads(
        lx_m=req.lx_m,
        ly_m=req.ly_m,
        live_load_kN_m2=req.live_load_kN_m2,
        floor_finish_kN_m2=req.floor_finish_kN_m2 or 1.0,
        support_width_mm=req.support_width_mm or 230.0,
        fck=req.fck or 25.0,
        fy=req.fy or 500.0,
        exposure=req.exposure or "Moderate",
        support_condition=req.support_condition or "simply_supported",
    )
    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
    log_audit_event(
        key_name=key_name,
        query=f"design_slab_review lx={req.lx_m}m ly={req.ly_m}m LL={req.live_load_kN_m2}kN/m2",
        k=0,
        returned_chunk_ids=[],
        rerank_scores=[],
        latency_ms=latency_ms,
        status_code=200,
    )
    return sizing_res


class SlabDxfRequest(BaseModel):
    lx_m: float = Field(..., gt=0, description="Shorter slab span in meters")
    ly_m: float = Field(..., gt=0, description="Longer slab span in meters")
    live_load_kN_m2: float = Field(..., gt=0, description="Service live/imposed load in kN/m2")
    floor_finish_kN_m2: Optional[float] = Field(1.0, ge=0, description="Floor finish load in kN/m2")
    support_width_mm: Optional[float] = Field(230.0, gt=0, description="Width of supporting wall/beam in mm")
    fck: Optional[float] = Field(25.0, description="Concrete compressive strength in N/mm2")
    fy: Optional[float] = Field(500.0, description="Steel yield strength in N/mm2")
    exposure: Optional[str] = Field("Moderate", description="Environmental exposure condition")
    support_condition: Optional[str] = Field("simply_supported", description="Support condition")
    output_filename: Optional[str] = Field("slab_design.dxf", description="Output DXF filename")


@app.post("/v1/design/slab/dxf")
def design_slab_dxf_endpoint(req: SlabDxfRequest, key_name: str = Depends(verify_api_key)):
    """
    Pillar 1: IS 456 RC Slab 2D CAD DXF Export endpoint.
    Computes slab design and generates 2D AutoCAD blueprint with cross-section, plan layout, and title block.
    """
    start_time = time.perf_counter()
    sizing_res = size_slab_from_loads(
        lx_m=req.lx_m,
        ly_m=req.ly_m,
        live_load_kN_m2=req.live_load_kN_m2,
        floor_finish_kN_m2=req.floor_finish_kN_m2 or 1.0,
        support_width_mm=req.support_width_mm or 230.0,
        fck=req.fck or 25.0,
        fy=req.fy or 500.0,
        exposure=req.exposure or "Moderate",
        support_condition=req.support_condition or "simply_supported",
    )
    if sizing_res.get("status") == "needs_review":
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        log_audit_event(
            key_name=key_name,
            query=f"design_slab_dxf needs_review lx={req.lx_m}m ly={req.ly_m}m",
            k=0,
            returned_chunk_ids=[],
            rerank_scores=[],
            latency_ms=latency_ms,
            status_code=200,
        )
        return sizing_res

    cad_dir = Path("data/processed/cad")
    cad_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(req.output_filename or "slab_design.dxf").name
    out_path = cad_dir / filename

    dxf_result = export_slab_dxf(
        design=sizing_res["design_dict"],
        output_path=str(out_path),
    )
    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
    log_audit_event(
        key_name=key_name,
        query=f"design_slab_dxf output={filename}",
        k=0,
        returned_chunk_ids=[],
        rerank_scores=[],
        latency_ms=latency_ms,
        status_code=200,
    )
    return {
        "status": dxf_result["status"],
        "dxf_path": dxf_result["dxf_path"],
        "slab_type": dxf_result["slab_type"],
        "dimensions": dxf_result["dimensions"],
        "main_reinforcement": dxf_result["main_reinforcement"],
        "transverse_reinforcement": dxf_result["transverse_reinforcement"],
        "approval_status": dxf_result["approval_status"],
    }


class FootingReviewRequest(BaseModel):
    axial_load_kN: float = Field(..., gt=0, description="Column service axial load in kN (unfactored)")
    sbc_kN_m2: Optional[float] = Field(200.0, gt=0, description="Soil safe bearing capacity in kN/m2 (default 200.0)")
    col_b_mm: Optional[float] = Field(400.0, gt=0, description="Column width in mm (default 400.0)")
    col_D_mm: Optional[float] = Field(400.0, gt=0, description="Column depth in mm (default 400.0)")
    fck: Optional[float] = Field(25.0, description="Concrete compressive strength in N/mm2 (default 25.0)")
    fy: Optional[float] = Field(500.0, description="Steel yield strength in N/mm2 (default 500.0)")


@app.post("/v1/design/footing/review")
def design_footing_review_endpoint(req: FootingReviewRequest, key_name: str = Depends(verify_api_key)):
    """
    Pillar 1: IS 456 RC Isolated Footing Design & Sizing endpoint.
    Computes plan dimensions (B x L), depth for punching shear, flexural steel mesh, and soil checks.
    """
    start_time = time.perf_counter()
    sizing_res = size_footing_from_load(
        axial_load_kN=req.axial_load_kN,
        sbc_kN_m2=req.sbc_kN_m2 or 200.0,
        col_b_mm=req.col_b_mm or 400.0,
        col_D_mm=req.col_D_mm or 400.0,
        fck=req.fck or 25.0,
        fy=req.fy or 500.0,
    )
    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
    log_audit_event(
        key_name=key_name,
        query=f"design_footing_review axial={req.axial_load_kN}kN sbc={req.sbc_kN_m2}kN/m2",
        k=0,
        returned_chunk_ids=[],
        rerank_scores=[],
        latency_ms=latency_ms,
        status_code=200,
    )
    return sizing_res


class FootingDxfRequest(BaseModel):
    axial_load_kN: float = Field(..., gt=0, description="Column service axial load in kN")
    sbc_kN_m2: Optional[float] = Field(200.0, gt=0, description="Soil safe bearing capacity in kN/m2")
    col_b_mm: Optional[float] = Field(400.0, gt=0, description="Column width in mm")
    col_D_mm: Optional[float] = Field(400.0, gt=0, description="Column depth in mm")
    fck: Optional[float] = Field(25.0, description="Concrete compressive strength in N/mm2")
    fy: Optional[float] = Field(500.0, description="Steel yield strength in N/mm2")
    output_filename: Optional[str] = Field("footing_design.dxf", description="Output DXF filename")


@app.post("/v1/design/footing/dxf")
def design_footing_dxf_endpoint(req: FootingDxfRequest, key_name: str = Depends(verify_api_key)):
    """
    Pillar 1: IS 456 RC Isolated Footing 2D CAD DXF Export endpoint.
    Generates 2D AutoCAD blueprint with plan view, elevation section, starter dowels, and bottom mesh.
    """
    start_time = time.perf_counter()
    sizing_res = size_footing_from_load(
        axial_load_kN=req.axial_load_kN,
        sbc_kN_m2=req.sbc_kN_m2 or 200.0,
        col_b_mm=req.col_b_mm or 400.0,
        col_D_mm=req.col_D_mm or 400.0,
        fck=req.fck or 25.0,
        fy=req.fy or 500.0,
    )
    if sizing_res.get("status") == "needs_review":
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        log_audit_event(
            key_name=key_name,
            query=f"design_footing_dxf needs_review axial={req.axial_load_kN}kN",
            k=0,
            returned_chunk_ids=[],
            rerank_scores=[],
            latency_ms=latency_ms,
            status_code=200,
        )
        return sizing_res

    cad_dir = Path("data/processed/cad")
    cad_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(req.output_filename or "footing_design.dxf").name
    out_path = cad_dir / filename

    dxf_result = export_footing_dxf(
        design=sizing_res["design_dict"],
        output_path=str(out_path),
    )
    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
    log_audit_event(
        key_name=key_name,
        query=f"design_footing_dxf output={filename}",
        k=0,
        returned_chunk_ids=[],
        rerank_scores=[],
        latency_ms=latency_ms,
        status_code=200,
    )
    return {
        "status": dxf_result["status"],
        "dxf_path": dxf_result["dxf_path"],
        "plan_dimensions": dxf_result["plan_dimensions"],
        "total_depth": dxf_result["total_depth"],
        "reinforcement": dxf_result["reinforcement"],
        "approval_status": dxf_result["approval_status"],
    }


@app.get("/v1/cad/download/{filename}")
def download_cad_file(filename: str):
    """
    Direct 2D CAD DXF file download endpoint for the web frontend.
    Safely retrieves generated DXF files from data/processed/cad/ or the root workspace.
    """
    safe_name = Path(filename).name
    project_root = Path(__file__).resolve().parent.parent.parent
    candidates = [
        project_root / "data" / "processed" / "cad" / safe_name,
        Path("data/processed/cad") / safe_name,
        project_root / safe_name,
        Path(safe_name),
    ]
    for p in candidates:
        if p.exists() and p.is_file() and p.suffix.lower() == ".dxf":
            return FileResponse(
                path=str(p),
                filename=safe_name,
                media_type="application/dxf",
            )
    raise HTTPException(status_code=404, detail=f"CAD drawing '{safe_name}' not found.")



class MultiCodeQueryRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Search query across structural standards")
    code: Optional[str] = Field(None, description="Optional standard filter: 'IS 456', 'IS 13920', or 'IS 875'")
    top_k: Optional[int] = Field(3, ge=1, le=10, description="Number of results to return (default 3)")


@app.post("/v1/rag/multicode/query")
def multicode_rag_query_endpoint(req: MultiCodeQueryRequest, key_name: str = Depends(verify_api_key)):
    """
    Multi-Standard Structural RAG Search Endpoint.
    Searches across IS 456:2000, IS 13920:2016 (Seismic), and IS 875 (Imposed Loads).
    """
    start_time = time.perf_counter()
    results = retrieve_multicode(
        query=req.query,
        code_filter=req.code,
        top_k=req.top_k or 3,
    )
    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
    log_audit_event(
        key_name=key_name,
        query=f"multicode_query [{req.code or 'ALL'}]: {req.query}",
        k=len(results),
        returned_chunk_ids=[r["chunk_id"] for r in results],
        rerank_scores=[r["score"] for r in results],
        latency_ms=latency_ms,
        status_code=200,
    )
    return {
        "query": req.query,
        "code_filter": req.code or "ALL",
        "total_results": len(results),
        "results": results,
    }


class SeismicComplianceRequest(BaseModel):
    member_type: str = Field(..., description="'beam' or 'column'")
    b_mm: float = Field(..., gt=0, description="Width in mm")
    D_mm: float = Field(..., gt=0, description="Total depth in mm")
    d_mm: Optional[float] = Field(None, description="Effective depth for beams in mm")
    clear_height_mm: Optional[float] = Field(None, description="Clear unsupported height for columns in mm")
    fck: float = Field(..., ge=15, le=80, description="Concrete compressive strength (N/mm2)")
    fy: float = Field(..., ge=250, le=600, description="Steel yield strength (N/mm2)")
    ast_provided_mm2: Optional[float] = Field(None, description="Longitudinal steel area in mm2")
    stirrup_or_tie_dia_mm: Optional[float] = Field(8.0, description="Transverse tie/stirrup diameter in mm")
    db_min_mm: Optional[float] = Field(16.0, description="Smallest longitudinal bar diameter in mm")
    seismic_zone: Optional[str] = Field("IV", description="Seismic Zone: II, III, IV, or V")
    is_ductile: Optional[bool] = Field(True, description="Enforce IS 13920 ductile detailing")


@app.post("/v1/validation/seismic-compliance")
def seismic_compliance_endpoint(req: SeismicComplianceRequest, key_name: str = Depends(verify_api_key)):
    """
    Step 6 Compliance Reasoning Engine:
    Resolves conflicts between IS 456:2000 (General) and IS 13920:2016 (Seismic Ductile Detailing).
    Determines governing requirements for beams and columns.
    """
    start_time = time.perf_counter()
    m_type = req.member_type.lower()

    if m_type == "beam":
        effective_d = req.d_mm or (req.D_mm - 50.0)
        ast = req.ast_provided_mm2 or (0.01 * req.b_mm * effective_d)
        res = resolve_beam_seismic_conflicts(
            b=req.b_mm,
            D=req.D_mm,
            d=effective_d,
            fck=req.fck,
            fy=req.fy,
            ast_provided=ast,
            stirrup_dia=req.stirrup_or_tie_dia_mm or 8.0,
            stirrup_spacing_midspan=150.0,
            db_min=req.db_min_mm or 16.0,
            seismic_zone=req.seismic_zone or "IV",
            is_ductile=req.is_ductile if req.is_ductile is not None else True,
        )
    elif m_type == "column":
        height = req.clear_height_mm or 3000.0
        res = resolve_column_seismic_conflicts(
            b=req.b_mm,
            D=req.D_mm,
            clear_height=height,
            fck=req.fck,
            fy=req.fy,
            db_min=req.db_min_mm or 16.0,
            tie_dia=req.stirrup_or_tie_dia_mm or 8.0,
            seismic_zone=req.seismic_zone or "IV",
            is_ductile=req.is_ductile if req.is_ductile is not None else True,
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid member_type. Must be 'beam' or 'column'.")

    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
    log_audit_event(
        key_name=key_name,
        query=f"seismic_compliance {m_type} zone={req.seismic_zone}",
        k=len(res.get("checks", [])),
        returned_chunk_ids=[],
        rerank_scores=[],
        latency_ms=latency_ms,
        status_code=200,
    )
    return res


class SeismicBaseShearRequest(BaseModel):
    height_m: float = Field(..., gt=0, description="Building height in meters")
    total_weight_kN: float = Field(..., gt=0, description="Total building seismic weight W in kN")
    base_dim_m: Optional[float] = Field(None, gt=0, description="Base plan dimension in meters along considered direction")
    seismic_zone: Optional[str] = Field("IV", description="Seismic zone: II, III, IV, or V")
    occupancy: Optional[str] = Field("residential", description="Occupancy type: hospital, school, residential, dense_commercial")
    structural_system: Optional[str] = Field("rc_smrf", description="Lateral system: rc_smrf, rc_omrf, steel_cbf, steel_ebf")
    soil_type: Optional[str] = Field("medium", description="Soil type: rock, medium, or soft")
    storey_height_m: Optional[float] = Field(3.0, gt=0, description="Storey height in meters for drift check")


@app.post("/v1/design/seismic/base-shear")
def seismic_base_shear_endpoint(req: SeismicBaseShearRequest, key_name: str = Depends(verify_api_key)):
    """
    Step 6 Deterministic Calculation Engine:
    Calculates fundamental period (Ta), spectral acceleration (Sa/g), seismic coefficient (Ah),
    and total design base shear (VB) per IS 1893 (Part 1):2016.
    """
    start_time = time.perf_counter()
    res = calculate_seismic_base_shear(
        height_m=req.height_m,
        total_weight_kN=req.total_weight_kN,
        base_dim_m=req.base_dim_m,
        seismic_zone=req.seismic_zone or "IV",
        occupancy=req.occupancy or "residential",
        structural_system=req.structural_system or "rc_smrf",
        soil_type=req.soil_type or "medium",
        storey_height_m=req.storey_height_m or 3.0,
    )
    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
    log_audit_event(
        key_name=key_name,
        query=f"seismic_base_shear h={req.height_m}m zone={req.seismic_zone}",
        k=0,
        returned_chunk_ids=[],
        rerank_scores=[],
        latency_ms=latency_ms,
        status_code=200,
    )
    return res


@app.get("/v1/audit/summary")
def get_audit_summary(limit: int = 200) -> Dict[str, Any]:
    """
    Step 10 Production Observability Endpoint:
    Aggregates request latencies, status codes, query volumes, and top-retrieved clauses
    from data/audit/audit.jsonl.
    """
    if not AUDIT_LOG_FILE.exists():
        return {
            "status": "empty",
            "message": "No audit records found yet.",
            "total_queries_logged": 0,
        }

    records = []
    try:
        with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        records.append(json.loads(line.strip()))
                    except Exception:
                        continue
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read audit log: {e}")

    if not records:
        return {
            "status": "empty",
            "total_queries_logged": 0,
        }

    total_count = len(records)
    latencies = [float(r["latency_ms"]) for r in records if "latency_ms" in r and r["latency_ms"] is not None]

    # Calculate statistics
    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
    sorted_lat = sorted(latencies)
    p50 = round(sorted_lat[len(sorted_lat) // 2], 2) if sorted_lat else 0.0
    p95_idx = int(0.95 * len(sorted_lat))
    p95 = round(sorted_lat[min(p95_idx, len(sorted_lat) - 1)], 2) if sorted_lat else 0.0
    min_lat = round(sorted_lat[0], 2) if sorted_lat else 0.0
    max_lat = round(sorted_lat[-1], 2) if sorted_lat else 0.0

    # Status codes
    status_codes: Dict[str, int] = {}
    for r in records:
        sc = str(r.get("status_code", 200))
        status_codes[sc] = status_codes.get(sc, 0) + 1

    # Clause frequencies
    clause_counts: Dict[str, int] = {}
    for r in records:
        for cid in r.get("returned_chunk_ids", []):
            clause_counts[cid] = clause_counts.get(cid, 0) + 1

    top_clauses = [
        {"clause_id": cid, "retrieval_count": cnt}
        for cid, cnt in sorted(clause_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    ]

    # Unique callers
    callers = sorted(list({r.get("key_name", "anonymous") for r in records if r.get("key_name")}))

    # Recent queries (last 5)
    recent = []
    for r in records[-5:]:
        recent.append({
            "timestamp": r.get("timestamp"),
            "key_name": r.get("key_name"),
            "query": r.get("query"),
            "latency_ms": r.get("latency_ms"),
            "status_code": r.get("status_code"),
            "top_clause": r.get("returned_chunk_ids", [None])[0] if r.get("returned_chunk_ids") else None,
        })

    return {
        "status": "healthy",
        "total_queries_logged": total_count,
        "latency_statistics_ms": {
            "average": avg_latency,
            "median_p50": p50,
            "p95": p95,
            "min": min_lat,
            "max": max_lat,
        },
        "status_code_distribution": status_codes,
        "top_retrieved_clauses": top_clauses,
        "unique_authorized_keys": callers,
        "recent_queries": recent,
    }







