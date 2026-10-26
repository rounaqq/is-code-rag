"""
Tests for IS 456 beam design proposal generator with safety guards (src/generation/design_proposal.py).
Uses fake LLM functions returning fixed JSON payloads. Does NOT call network or read .env.
"""

import json
import re
import pytest
from src.generation.design_proposal import propose

SAMPLE_REQUEST = {
    "b": 300,
    "D": 500,
    "d": 450,
    "fck": 25,
    "fy": 500,
    "exposure": "Moderate",
    "question": "maximum tension reinforcement in a beam and minimum shear stirrups",
}


def _extract_first_chunk_id(user_prompt: str) -> str:
    """Extracts a valid chunk_id present in the prompt's retrieved set."""
    match = re.search(r"Chunk ID:\s*([A-Za-z0-9\-().]+)", user_prompt)
    if match:
        return match.group(1)
    return "IS456-2000-CL-26.5.1.1(a)"


def test_valid_proposal_accepted():
    """A valid proposal gives 'accepted', correct cover_mm, and passing checks."""
    def fake_llm(system: str, user: str) -> str:
        cid = _extract_first_chunk_id(user)
        return json.dumps({
            "main_bar_dia_mm": 16,
            "main_bar_count": 3,
            "stirrup_dia_mm": 8,
            "stirrup_spacing_mm": 150,
            "compression_bar_dia_mm": 12,
            "compression_bar_count": 2,
            "citations": [cid],
            "reasoning": "Valid reinforcement proposal satisfying IS 456 limits.",
            "insufficient_information": False,
        })

    res = propose(SAMPLE_REQUEST, llm=fake_llm)
    assert res["status"] == "accepted"
    assert res["proposal"] is not None
    assert res["cover_mm"] == 30  # Moderate exposure from Table 16
    assert len(res["checks"]) > 0
    assert all(c["passed"] for c in res["checks"])
    assert "Passes the implemented IS 456 beam detailing checks only" in res["notes"]


def test_citation_not_in_retrieved_set_rejected():
    """A citation not in the retrieved set gives 'rejected'."""
    def fake_llm(system: str, user: str) -> str:
        return json.dumps({
            "main_bar_dia_mm": 16,
            "main_bar_count": 3,
            "stirrup_dia_mm": 8,
            "stirrup_spacing_mm": 150,
            "citations": ["IS456-INVALID-CHUNK-999"],
            "reasoning": "Uses invalid non-retrieved citation.",
            "insufficient_information": False,
        })

    res = propose(SAMPLE_REQUEST, llm=fake_llm)
    assert res["status"] == "rejected"
    assert "not in retrieved set" in res["notes"]


def test_stirrup_spacing_400_needs_review():
    """Stirrup spacing 400 gives 'needs_review' with the spacing check failed."""
    def fake_llm(system: str, user: str) -> str:
        cid = _extract_first_chunk_id(user)
        return json.dumps({
            "main_bar_dia_mm": 16,
            "main_bar_count": 3,
            "stirrup_dia_mm": 8,
            "stirrup_spacing_mm": 400,  # Exceeds max spacing (limit is min(0.75*450=337.5, 300) = 300 mm)
            "citations": [cid],
            "reasoning": "Spacing of 400 mm exceeds code limit.",
            "insufficient_information": False,
        })

    res = propose(SAMPLE_REQUEST, llm=fake_llm)
    assert res["status"] == "needs_review"
    spacing_check = next((c for c in res["checks"] if c["check"] == "max_stirrup_spacing"), None)
    assert spacing_check is not None
    assert spacing_check["passed"] is False
    assert spacing_check["required"] == 300.0
    assert spacing_check["provided"] == 400.0


def test_invalid_json_rejected():
    """Invalid JSON response gives 'rejected' and includes diagnostic info."""
    def fake_llm(system: str, user: str) -> str:
        return "Not valid JSON at all: error in syntax {"

    res = propose(SAMPLE_REQUEST, llm=fake_llm)
    assert res["status"] == "rejected"
    assert res["proposal"] is None
    assert "invalid JSON" in res["notes"]
    assert "diagnostic" in res
    assert res["diagnostic"]["reply_length"] == len("Not valid JSON at all: error in syntax {")


def test_fake_llm_not_json_diagnostic_and_security(monkeypatch):
    """Fake LLM returning 'not json' produces diagnostic fields and leaks no URL or token."""
    secret_token = "secret_llm_token_abc_xyz_98765"
    sensitive_url = "http://super-secret-host.internal:11434"
    monkeypatch.setenv("OLLAMA_API_TOKEN", secret_token)
    monkeypatch.setenv("OLLAMA_BASE_URL", sensitive_url)

    fake_reply = "not json"

    def fake_llm(system: str, user: str) -> str:
        return fake_reply

    fake_llm.last_response_info = {
        "done_reason": "stop",
        "eval_count": 45,
        "prompt_eval_count": 20,
        "thinking_present": True,
    }

    res = propose(SAMPLE_REQUEST, llm=fake_llm)

    # Status check
    assert res["status"] == "rejected"
    assert res["proposal"] is None

    # Diagnostic fields check
    assert "diagnostic" in res
    diag = res["diagnostic"]
    assert diag["reply_length"] == len(fake_reply)
    assert diag["first_300"] == fake_reply
    assert diag["last_100"] == fake_reply
    assert diag["done_reason"] == "stop"
    assert diag["eval_count"] == 45
    assert diag["prompt_eval_count"] == 20
    assert diag["thinking_present"] is True

    # Security check: zero URL or token leakage in entire result
    result_str = json.dumps(res)
    assert secret_token not in result_str
    assert sensitive_url not in result_str
    assert "Authorization" not in result_str
    assert "headers" not in res
    assert "request" not in res


def test_fake_llm_not_json_long_reply_diagnostic():
    """Verify first 300 and last 100 character slices with long reply."""
    long_reply = "PREFIX_" + ("X" * 350) + "_MIDDLE_" + ("Y" * 150) + "_SUFFIX"

    def fake_llm(system: str, user: str) -> str:
        return long_reply

    fake_llm.last_response_info = {
        "done_reason": "length",
        "eval_count": 500,
        "prompt_eval_count": 50,
        "thinking_present": False,
    }

    res = propose(SAMPLE_REQUEST, llm=fake_llm)
    assert res["status"] == "rejected"
    assert "diagnostic" in res
    diag = res["diagnostic"]
    assert diag["reply_length"] == len(long_reply)
    assert diag["first_300"] == long_reply[:300]
    assert diag["last_100"] == long_reply[-100:]
    assert diag["done_reason"] == "length"
    assert diag["eval_count"] == 500
    assert diag["prompt_eval_count"] == 50
    assert diag["thinking_present"] is False


def test_fake_llm_timeout_diagnostic_and_security(monkeypatch):
    """Fake LLM raising RuntimeError('timeout') sets notes error type, diagnostic fields, and leaks no URL or token."""
    secret_token = "secret_llm_token_timeout_54321"
    sensitive_url = "http://super-secret-host-timeout.internal:11434"
    monkeypatch.setenv("OLLAMA_API_TOKEN", secret_token)
    monkeypatch.setenv("OLLAMA_BASE_URL", sensitive_url)

    def fake_llm_timeout(system: str, user: str) -> str:
        raise RuntimeError("timeout")

    res = propose(SAMPLE_REQUEST, llm=fake_llm_timeout)

    assert res["status"] == "rejected"
    assert res["proposal"] is None
    # Check error type in notes
    assert "timeout" in res["notes"]

    # Check diagnostic fields exist
    assert "diagnostic" in res
    diag = res["diagnostic"]
    assert "reply_length" in diag
    assert "first_300" in diag
    assert "last_100" in diag
    assert "done_reason" in diag
    assert "eval_count" in diag
    assert "prompt_eval_count" in diag
    assert "thinking_present" in diag

    # Security check: zero URL or token leakage in entire result
    result_str = json.dumps(res)
    assert secret_token not in result_str
    assert sensitive_url not in result_str
    assert "Authorization" not in result_str
    assert "headers" not in res
    assert "request" not in res


@pytest.mark.parametrize(
    "error_msg,expected_note",
    [
        ("timeout", "timeout"),
        ("connection error", "connection error"),
        ("HTTP 500", "HTTP 500"),
        ("HTTP 404", "HTTP 404"),
        ("other unexpected error", "other"),
    ],
)
def test_llm_call_error_types_in_notes(error_msg, expected_note):
    """LLM call failure error types are correctly mapped and added to notes."""
    def fake_llm(system: str, user: str) -> str:
        raise RuntimeError(error_msg)

    res = propose(SAMPLE_REQUEST, llm=fake_llm)
    assert res["status"] == "rejected"
    assert expected_note in res["notes"]
    assert "diagnostic" in res


def test_insufficient_information_true_needs_review():
    """insufficient_information true gives 'needs_review' and includes reasoning in notes."""
    def fake_llm(system: str, user: str) -> str:
        cid = _extract_first_chunk_id(user)
        return json.dumps({
            "main_bar_dia_mm": 16,
            "main_bar_count": 3,
            "stirrup_dia_mm": 8,
            "stirrup_spacing_mm": 150,
            "citations": [cid],
            "reasoning": "Clauses do not contain sufficient information.",
            "insufficient_information": True,
        })

    res = propose(SAMPLE_REQUEST, llm=fake_llm)
    assert res["status"] == "needs_review"
    assert res["proposal"]["insufficient_information"] is True
    assert "Clauses do not contain sufficient information." in res["notes"]


def test_empty_citations_rejected():
    """Empty citations gives 'rejected'."""
    def fake_llm(system: str, user: str) -> str:
        return json.dumps({
            "main_bar_dia_mm": 16,
            "main_bar_count": 3,
            "stirrup_dia_mm": 8,
            "stirrup_spacing_mm": 150,
            "citations": [],
            "reasoning": "No citations provided.",
            "insufficient_information": False,
        })

    res = propose(SAMPLE_REQUEST, llm=fake_llm)
    assert res["status"] == "rejected"
    assert "citations list is empty" in res["notes"]


def test_all_null_reply_insufficient_information_needs_review():
    """All-null reply with insufficient_information true gives 'needs_review' with model reasoning in notes."""
    def fake_llm(system: str, user: str) -> str:
        return json.dumps({
            "main_bar_dia_mm": None,
            "main_bar_count": None,
            "stirrup_dia_mm": None,
            "stirrup_spacing_mm": None,
            "compression_bar_dia_mm": None,
            "compression_bar_count": None,
            "citations": [],
            "reasoning": "The retrieved clauses do not provide beam detailing parameters.",
            "insufficient_information": True,
        })

    res = propose(SAMPLE_REQUEST, llm=fake_llm)
    assert res["status"] == "needs_review"
    assert res["proposal"] is not None
    assert res["proposal"]["insufficient_information"] is True
    assert "The retrieved clauses do not provide beam detailing parameters." in res["notes"]
    assert res["checks"] == []


def test_insufficient_information_false_null_bar_count_rejected():
    """insufficient_information false with null bar count gives 'rejected' and note names the field."""
    def fake_llm(system: str, user: str) -> str:
        cid = _extract_first_chunk_id(user)
        return json.dumps({
            "main_bar_dia_mm": 16,
            "main_bar_count": None,
            "stirrup_dia_mm": 8,
            "stirrup_spacing_mm": 150,
            "citations": [cid],
            "reasoning": "Main bar count is missing.",
            "insufficient_information": False,
        })

    res = propose(SAMPLE_REQUEST, llm=fake_llm)
    assert res["status"] == "rejected"
    assert "main_bar_count" in res["notes"]
    assert "invalid JSON" not in res["notes"]


def test_non_json_text_rejected_with_invalid_json():
    """Non-JSON text gives 'rejected' with 'invalid JSON'."""
    def fake_llm(system: str, user: str) -> str:
        return "This is completely raw plain text, not JSON at all."

    res = propose(SAMPLE_REQUEST, llm=fake_llm)
    assert res["status"] == "rejected"
    assert "invalid JSON" in res["notes"]


