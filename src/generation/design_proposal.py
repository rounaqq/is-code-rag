"""
IS 456 Structural Beam Design Proposal Generator with Safety Guards.
Combines retrieval, LLM parameter extraction, citation validation,
and deterministic IS 456 code verification checks.
Does NOT import, read, print, or quote .env or any secret keys.
"""

import json
import math
from typing import Dict, Any, Optional, List, Callable
import httpx
from pydantic import BaseModel, Field, ValidationError

from src.generation.llm_client import complete_json
from src.retrieval.pipeline import retrieve
from src.validation.is456_checks import (
    nominal_cover,
    min_tension_steel,
    max_tension_steel,
    max_compression_steel,
    max_stirrup_spacing,
    min_shear_steel,
)

BASE_NOTE = (
    "Passes the implemented IS 456 beam detailing checks only; "
    "not a full design check. A structural engineer must review."
)

SYSTEM_PROMPT = """You are a structural engineering detailing assistant for IS 456:2000.
Use ONLY the clauses provided in the prompt.
Never use any value or limit from memory.
Never do arithmetic for limits.
Answer with JSON only.
If the clauses do not contain what is needed to propose detailing, set "insufficient_information" to true.

JSON schema:
{
  "main_bar_dia_mm": <number>,
  "main_bar_count": <integer>,
  "stirrup_dia_mm": <number>,
  "stirrup_spacing_mm": <number>,
  "compression_bar_dia_mm": <number or null>,
  "compression_bar_count": <integer or null>,
  "citations": [<list of chunk_id strings from the provided clauses>],
  "reasoning": "<short reasoning>",
  "insufficient_information": <boolean>
}"""


class LLMProposal(BaseModel):
    main_bar_dia_mm: Optional[float] = Field(default=None, gt=0)
    main_bar_count: Optional[int] = Field(default=None, ge=1)
    stirrup_dia_mm: Optional[float] = Field(default=None, gt=0)
    stirrup_spacing_mm: Optional[float] = Field(default=None, gt=0)
    compression_bar_dia_mm: Optional[float] = Field(default=None, gt=0)
    compression_bar_count: Optional[int] = Field(default=None, ge=0)
    citations: Optional[List[str]] = Field(default=None)
    reasoning: str = ""
    insufficient_information: bool = False


def _clean_json_text(text: str) -> str:
    """Strips markdown code fences if present."""
    raw = text.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    return raw


def propose(request: Dict[str, Any], llm: Optional[Callable[[str, str], str]] = None) -> Dict[str, Any]:
    """
    Generates and validates an IS 456 beam reinforcement detailing proposal.

    Args:
        request: Dict with keys b, D, d (or span_m, dead_load_kN_per_m, live_load_kN_per_m),
                 fck, fy, exposure, question.
        llm: Callable (system: str, user: str) -> str. Defaults to complete_json.

    Returns:
        Dict with status ("accepted", "needs_review", "rejected"), proposal,
        retrieved_chunk_ids, checks, cover_mm, notes.
    """
    llm_func = llm if llm is not None else complete_json

    # Support preliminary sizing from Span and Loads if b, D, d are not provided
    req = dict(request)
    if "span_m" in req and (req.get("b") is None or req.get("D") is None or req.get("d") is None):
        from src.generation.beam_sizing import size_beam_from_loads
        sizing_res = size_beam_from_loads(
            span_m=float(req["span_m"]),
            dead_load_kN_per_m=float(req.get("dead_load_kN_per_m", req.get("dead_load", 0.0))),
            live_load_kN_per_m=float(req.get("live_load_kN_per_m", req.get("live_load", 0.0))),
            fck=float(req.get("fck", 25.0)),
            fy=float(req.get("fy", 500.0)),
            exposure=str(req.get("exposure", "Moderate")),
            b=req.get("b"),
        )
        req["b"] = sizing_res["section_dimensions"]["b"]
        req["D"] = sizing_res["section_dimensions"]["D"]
        req["d"] = sizing_res["section_dimensions"]["d"]
        req["_sizing"] = sizing_res

    # a. Retrieve top-5 relevant chunks
    question = req.get("question", "")
    retrieved_chunks = retrieve(question, k=5)
    retrieved_chunk_ids = [c["chunk_id"] for c in retrieved_chunks]

    # e. Nominal cover from Table 16 (never decided by LLM)
    exposure = req.get("exposure", "")
    cover_res = nominal_cover(exposure)
    cover_mm = cover_res["required"]

    # Format retrieved clauses for user prompt
    clauses_text_list = []
    for c in retrieved_chunks:
        clauses_text_list.append(
            f"Chunk ID: {c['chunk_id']}\nCitation: {c['citation']}\nTitle: {c['title']}\nText: {c['text']}"
        )
    formatted_clauses = "\n\n---\n\n".join(clauses_text_list)

    user_prompt = f"""Beam Design Parameters:
- Breadth (b): {req.get('b')} mm
- Total Depth (D): {req.get('D')} mm
- Effective Depth (d): {req.get('d')} mm
- Characteristic Compressive Strength (fck): {req.get('fck')} N/mm2
- Steel Yield Strength (fy): {req.get('fy')} N/mm2
- Exposure Condition: {req.get('exposure')}
- Engineer Request: {question}

Retrieved IS 456:2000 Reference Clauses:
{formatted_clauses}

Propose reinforcement detailing matching these parameters using only the retrieved clauses above."""

    # b. Call the LLM
    resp_info = {}
    if hasattr(llm_func, "last_response_info") and isinstance(llm_func.last_response_info, dict):
        resp_info = llm_func.last_response_info
    else:
        try:
            from src.generation.llm_client import get_last_response_info
            resp_info = get_last_response_info()
        except ImportError:
            resp_info = {}

    try:
        raw_llm_output = llm_func(SYSTEM_PROMPT, user_prompt)
    except Exception as exc:
        err_msg = str(exc).strip()
        if isinstance(exc, httpx.TimeoutException) or "timeout" in err_msg.lower():
            err_type = "timeout"
        elif (
            isinstance(exc, (httpx.ConnectError, ConnectionError))
            or "connection error" in err_msg.lower()
            or "connect" in err_msg.lower()
        ):
            err_type = "connection error"
        elif "http" in err_msg.lower() or isinstance(exc, httpx.HTTPStatusError):
            import re
            m = re.search(r"http\s*(\d+)", err_msg, re.IGNORECASE)
            if m:
                err_type = f"HTTP {m.group(1)}"
            elif hasattr(exc, "response") and hasattr(exc.response, "status_code"):
                err_type = f"HTTP {exc.response.status_code}"
            else:
                m_code = re.search(r"\b(\d{3})\b", err_msg)
                err_type = f"HTTP {m_code.group(1)}" if m_code else "HTTP error"
        else:
            err_type = "other"

        diagnostic = {
            "error_type": err_type,
            "reply_length": 0,
            "first_300": "",
            "last_100": "",
            "reply_first_300": "",
            "reply_last_100": "",
            "done_reason": resp_info.get("done_reason"),
            "eval_count": resp_info.get("eval_count"),
            "prompt_eval_count": resp_info.get("prompt_eval_count"),
            "thinking_present": bool(resp_info.get("thinking_present", False)),
        }

        return {
            "status": "rejected",
            "proposal": None,
            "retrieved_chunk_ids": retrieved_chunk_ids,
            "checks": [],
            "cover_mm": cover_mm,
            "notes": f"Proposal rejected: LLM call failure ({err_type}). {BASE_NOTE}",
            "diagnostic": diagnostic,
        }

    # Refresh response info after successful call if available
    if hasattr(llm_func, "last_response_info") and isinstance(llm_func.last_response_info, dict):
        resp_info = llm_func.last_response_info
    else:
        try:
            from src.generation.llm_client import get_last_response_info
            resp_info = get_last_response_info()
        except ImportError:
            pass

    done_reason = resp_info.get("done_reason")
    eval_count = resp_info.get("eval_count")
    prompt_eval_count = resp_info.get("prompt_eval_count")
    thinking_present = bool(resp_info.get("thinking_present", False))

    # c. Parse and validate JSON
    try:
        cleaned_json = _clean_json_text(raw_llm_output)
        data = json.loads(cleaned_json)
        if not isinstance(data, dict):
            raise json.JSONDecodeError("Expected JSON object", cleaned_json, 0)
    except Exception as exc:
        diagnostic = {
            "reply_length": len(raw_llm_output),
            "first_300": raw_llm_output[:300],
            "last_100": raw_llm_output[-100:] if len(raw_llm_output) >= 100 else raw_llm_output,
            "reply_first_300": raw_llm_output[:300],
            "reply_last_100": raw_llm_output[-100:] if len(raw_llm_output) >= 100 else raw_llm_output,
            "done_reason": done_reason,
            "eval_count": eval_count,
            "prompt_eval_count": prompt_eval_count,
            "thinking_present": thinking_present,
        }
        return {
            "status": "rejected",
            "proposal": None,
            "retrieved_chunk_ids": retrieved_chunk_ids,
            "checks": [],
            "cover_mm": cover_mm,
            "notes": f"Proposal rejected: invalid JSON response ({type(exc).__name__}). {BASE_NOTE}",
            "diagnostic": diagnostic,
        }

    try:
        proposal = LLMProposal(**data)
    except ValidationError as exc:
        missing_fields = []
        for err in exc.errors():
            loc = err.get("loc", ())
            if loc:
                missing_fields.append(str(loc[0]))
        fields_str = ", ".join(missing_fields) if missing_fields else "schema"
        return {
            "status": "rejected",
            "proposal": None,
            "retrieved_chunk_ids": retrieved_chunk_ids,
            "checks": [],
            "cover_mm": cover_mm,
            "notes": f"Proposal rejected: validation error on '{fields_str}'. {BASE_NOTE}",
        }

    proposal_dict = proposal.model_dump()

    # If insufficient_information is true:
    # status "needs_review", with the model's reasoning in notes.
    # An empty citations list is allowed in this case.
    if proposal.insufficient_information:
        if proposal.citations:
            missing_citations = [cid for cid in proposal.citations if cid not in retrieved_chunk_ids]
            if missing_citations:
                return {
                    "status": "rejected",
                    "proposal": proposal_dict,
                    "retrieved_chunk_ids": retrieved_chunk_ids,
                    "checks": [],
                    "cover_mm": cover_mm,
                    "notes": f"Proposal rejected: citations not in retrieved set: {missing_citations}. {BASE_NOTE}",
                }

        checks = []
        if (
            proposal.main_bar_dia_mm is not None
            and proposal.main_bar_count is not None
            and proposal.stirrup_dia_mm is not None
            and proposal.stirrup_spacing_mm is not None
        ):
            b = float(req["b"])
            D = float(req["D"])
            d = float(req["d"])
            fy = float(req["fy"])

            ast_provided = (math.pi * (proposal.main_bar_dia_mm ** 2) / 4.0) * proposal.main_bar_count
            checks.append(min_tension_steel(b=b, d=d, fy=fy, ast_provided=ast_provided))
            checks.append(max_tension_steel(b=b, D=D, ast_provided=ast_provided))

            if proposal.compression_bar_dia_mm and proposal.compression_bar_count and proposal.compression_bar_count > 0:
                asc_provided = (math.pi * (proposal.compression_bar_dia_mm ** 2) / 4.0) * proposal.compression_bar_count
                checks.append(max_compression_steel(b=b, D=D, asc_provided=asc_provided))

            checks.append(max_stirrup_spacing(d=d, spacing=proposal.stirrup_spacing_mm, inclined_45=False))
            asv_provided = 2.0 * (math.pi * (proposal.stirrup_dia_mm ** 2) / 4.0)
            checks.append(min_shear_steel(b=b, sv=proposal.stirrup_spacing_mm, fy=fy, asv_provided=asv_provided))

        return {
            "status": "needs_review",
            "proposal": proposal_dict,
            "retrieved_chunk_ids": retrieved_chunk_ids,
            "checks": checks,
            "cover_mm": cover_mm,
            "notes": proposal.reasoning if proposal.reasoning else f"Insufficient information. {BASE_NOTE}",
        }

    # If insufficient_information is false:
    # the required fields and non-empty citations are mandatory, otherwise status "rejected"
    # with the specific missing field named in notes (never the word "invalid JSON" for a validation problem).
    for field_name in ["main_bar_dia_mm", "main_bar_count", "stirrup_dia_mm", "stirrup_spacing_mm"]:
        if getattr(proposal, field_name) is None:
            return {
                "status": "rejected",
                "proposal": proposal_dict,
                "retrieved_chunk_ids": retrieved_chunk_ids,
                "checks": [],
                "cover_mm": cover_mm,
                "notes": f"Proposal rejected: missing required field '{field_name}' ({field_name.replace('_', ' ')}). {BASE_NOTE}",
            }

    if not proposal.citations:
        return {
            "status": "rejected",
            "proposal": proposal_dict,
            "retrieved_chunk_ids": retrieved_chunk_ids,
            "checks": [],
            "cover_mm": cover_mm,
            "notes": f"Proposal rejected: missing required field 'citations' (citations list is empty). {BASE_NOTE}",
        }

    missing_citations = [cid for cid in proposal.citations if cid not in retrieved_chunk_ids]
    if missing_citations:
        return {
            "status": "rejected",
            "proposal": proposal_dict,
            "retrieved_chunk_ids": retrieved_chunk_ids,
            "checks": [],
            "cover_mm": cover_mm,
            "notes": f"Proposal rejected: citations not in retrieved set: {missing_citations}. {BASE_NOTE}",
        }

    # f. Compute areas & run deterministic IS 456 checks
    b = float(req["b"])
    D = float(req["D"])
    d = float(req["d"])
    fy = float(req["fy"])

    checks = []

    # Main tension reinforcement area: pi * dia^2 / 4 * count
    ast_provided = (math.pi * (proposal.main_bar_dia_mm ** 2) / 4.0) * proposal.main_bar_count
    checks.append(min_tension_steel(b=b, d=d, fy=fy, ast_provided=ast_provided))
    checks.append(max_tension_steel(b=b, D=D, ast_provided=ast_provided))

    # Compression reinforcement (if provided and count > 0)
    if proposal.compression_bar_dia_mm and proposal.compression_bar_count and proposal.compression_bar_count > 0:
        asc_provided = (math.pi * (proposal.compression_bar_dia_mm ** 2) / 4.0) * proposal.compression_bar_count
        checks.append(max_compression_steel(b=b, D=D, asc_provided=asc_provided))

    # Max stirrup spacing using d
    checks.append(max_stirrup_spacing(d=d, spacing=proposal.stirrup_spacing_mm, inclined_45=False))

    # Min shear steel using two-legged stirrup area: 2 * (pi * dia^2 / 4)
    asv_provided = 2.0 * (math.pi * (proposal.stirrup_dia_mm ** 2) / 4.0)
    checks.append(min_shear_steel(b=b, sv=proposal.stirrup_spacing_mm, fy=fy, asv_provided=asv_provided))

    # g. Evaluate status
    all_checks_passed = all(c.get("passed", False) for c in checks)

    if not all_checks_passed:
        status = "needs_review"
    else:
        status = "accepted"

    return {
        "status": status,
        "proposal": proposal_dict,
        "retrieved_chunk_ids": retrieved_chunk_ids,
        "checks": checks,
        "cover_mm": cover_mm,
        "notes": BASE_NOTE,
    }
