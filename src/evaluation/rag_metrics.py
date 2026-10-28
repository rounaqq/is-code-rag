"""
RAGAS-style offline proxy metrics (rule-based, deterministic).

FRAMING (read before using any score here):
These functions implement rule-based *proxies* for three RAGAS metric
definitions - faithfulness, answer relevancy and context relevancy. They are
NOT the RAGAS library. The `ragas`/`trulens` packages are not installed and
never imported, and no network access is used. Claim grounding is rule-based
(regex claim extraction plus numeric matching), and "relevancy" is a secondary
proxy computed from the project's existing BGE-small (BAAI/bge-small-en-v1.5)
embeddings. Scores are deterministic for a fixed encoder and fixed inputs, so
they run inside pytest with no network.

Grounding rules:
  * clause answers      -> every number, identifier and clause reference in the
                           answer must appear in the retrieved chunks.
  * design explanations -> every number must match the calculator output (plus
                           explicitly declared standard constants); every cited
                           clause must appear in the retrieved chunk set. The
                           calculated numbers are NOT required to appear in the
                           chunks, because the calculator - not the retriever -
                           is their source of truth.

The retrieval figures (precision@k, recall@k, MRR) are computed directly from
the labelled benchmark questions and are not proxies.
"""

import math
import re
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

import numpy as np

EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"

# --- Claim extraction patterns -------------------------------------------------
# Clause / table / figure / annex references (e.g. "Cl. 26.5.1.1(a)", "Table 16").
CLAUSE_REF_PATTERN = re.compile(
    r"(?:cl\.?|clause)\s*\d+(?:\.\d+)*(?:\s*\([a-z0-9]+\))?"
    r"|table\s*\d+"
    r"|fig\.?\s*\d+"
    r"|annex\s+[a-z](?:\s*,?\s*[a-z])?(?:\s*-?\s*\d+(?:\.\d+)*)?",
    re.IGNORECASE,
)

# Standard / material identifiers (e.g. "IS 456:2000", "M25", "Fe 500").
IDENTIFIER_PATTERN = re.compile(
    r"\bis\s*\d+(?:\s*\(part\s*\d+\))?(?:\s*:\s*\d{4})?"
    r"|\bm\d{2,3}\b"
    r"|\bfe\s?\d{3}\b",
    re.IGNORECASE,
)

# Standalone numeric values (not glued to a preceding/following word char).
NUMBER_PATTERN = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w])")

_WHITESPACE_PATTERN = re.compile(r"\s+")


# --- Normalisation helpers -----------------------------------------------------
def _normalize(text: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", str(text)).strip().lower()


def _compact(text: str) -> str:
    """Lower-cased text with all whitespace removed (for identifier matching)."""
    return re.sub(r"\s+", "", str(text).lower())


def _numbers_in_text(text: str) -> List[float]:
    vals: List[float] = []
    for m in NUMBER_PATTERN.finditer(str(text)):
        try:
            vals.append(float(m.group(1)))
        except ValueError:
            continue
    return vals


def _numbers_in_obj(obj: Any) -> List[float]:
    """Recursively collects numeric leaf values from a nested dict/list structure."""
    out: List[float] = []
    if isinstance(obj, bool):
        return out
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            out.extend(_numbers_in_obj(v))
    elif isinstance(obj, (list, tuple, set)):
        for v in obj:
            out.extend(_numbers_in_obj(v))
    return out


def _number_matches(value: float, candidates: Sequence[float], rel_tol: float = 1e-3) -> bool:
    for c in candidates:
        if abs(value - c) <= max(1e-6, rel_tol * abs(c)):
            return True
    return False


def extract_claims(text: str) -> List[Dict[str, str]]:
    """
    Extracts atomic, checkable claims from an answer: clause references,
    identifiers and standalone numbers. Clause references and identifiers are
    consumed first so their digits are not double-counted as numbers.
    """
    claims: List[Dict[str, str]] = []
    working = str(text)

    def _consume(pattern: re.Pattern, claim_type: str) -> None:
        nonlocal working
        for m in pattern.finditer(working):
            claims.append({"type": claim_type, "value": m.group(0).strip()})
        working = pattern.sub(lambda mm: " " * len(mm.group(0)), working)

    _consume(CLAUSE_REF_PATTERN, "clause_ref")
    _consume(IDENTIFIER_PATTERN, "identifier")
    for m in NUMBER_PATTERN.finditer(working):
        claims.append({"type": "number", "value": m.group(1)})

    return claims


# --- Grounding -----------------------------------------------------------------
def build_context_index(chunks: Sequence[Any]) -> Dict[str, Any]:
    """
    Builds lookup structures from retrieved chunks. Accepts a list of either
    plain strings or chunk dicts carrying text/title/citation fields.
    """
    texts: List[str] = []
    for c in chunks:
        if isinstance(c, dict):
            parts = [
                str(c.get("citation") or ""),
                str(c.get("title") or ""),
                str(c.get("text") or ""),
            ]
            texts.append(" ".join(p for p in parts if p).strip())
        else:
            texts.append(str(c))

    joined = " ".join(texts)
    return {
        "texts": texts,
        "normalized": _normalize(joined),
        "compact": _compact(joined),
        "numbers": _numbers_in_text(joined),
    }


def _ground_claim(
    claim: Dict[str, str],
    *,
    context: Optional[Dict[str, Any]] = None,
    calculator_numbers: Optional[Sequence[float]] = None,
    calculator_compact: Optional[str] = None,
    declared_constants: Optional[Sequence[float]] = None,
) -> bool:
    ctype = claim["type"]
    value = claim["value"]

    if ctype == "number":
        try:
            num = float(value)
        except ValueError:
            return False
        candidates: List[float] = []
        if calculator_numbers is not None:
            # design mode: numbers must match the calculator output / declared
            # constants only. Calculated numbers are NOT required to appear in
            # the retrieved chunks.
            candidates.extend(calculator_numbers)
            if declared_constants:
                candidates.extend(float(x) for x in declared_constants)
        else:
            # clause mode: numbers must appear in the retrieved chunks.
            if context is not None:
                candidates.extend(context["numbers"])
        return _number_matches(num, candidates)

    if ctype == "identifier":
        token = _compact(value)
        if not token:
            return True
        if context is not None and token in context["compact"]:
            return True
        if calculator_compact is not None and token in calculator_compact:
            return True
        return False

    # clause_ref
    compact_ref = _compact(value)
    # The dotted/numeric body is the strongest signal (e.g. "26.5.1.1").
    digits = re.findall(r"\d+(?:\.\d+)*", value)
    if context is not None:
        if compact_ref and compact_ref in context["compact"]:
            return True
        for d in digits:
            if re.search(r"(?<![\d.])" + re.escape(d) + r"(?![\d.])", context["normalized"]):
                return True
    if calculator_compact is not None:
        if compact_ref and compact_ref in calculator_compact:
            return True
        for d in digits:
            if re.search(r"(?<![\d.])" + re.escape(d) + r"(?![\d.])", calculator_compact):
                return True
    return False


def faithfulness(
    answer: str,
    retrieved_chunks: Sequence[Any],
    *,
    mode: str = "clause",
    calculator_output: Optional[Any] = None,
    declared_constants: Optional[Sequence[float]] = None,
) -> Dict[str, Any]:
    """
    Computes claim-level faithfulness (supported claims / total claims).

    mode="clause": every claim is grounded against the retrieved chunks only.
    mode="design": numbers are grounded against the calculator output (plus the
                   declared standard constants); clause references against the
                   retrieved chunks; identifiers against the calculator output
                   or the retrieved chunks.
    """
    if mode not in ("clause", "design"):
        raise ValueError("mode must be 'clause' or 'design'")

    context = build_context_index(retrieved_chunks)
    claims = extract_claims(answer)

    calculator_numbers = None
    calculator_compact = None
    if mode == "design" and calculator_output is not None:
        calculator_numbers = _numbers_in_obj(calculator_output)
        calculator_compact = _compact(_collect_text(calculator_output))

    supported = 0
    unsupported: List[Dict[str, str]] = []
    counts = {"number": 0, "identifier": 0, "clause_ref": 0}

    for claim in claims:
        counts[claim["type"]] += 1
        ok = _ground_claim(
            claim,
            context=context if mode == "clause" else context,
            calculator_numbers=calculator_numbers,
            calculator_compact=calculator_compact,
            declared_constants=declared_constants if mode == "design" else None,
        )
        if ok:
            supported += 1
        else:
            unsupported.append(claim)

    total = len(claims)
    return {
        "mode": mode,
        "score": round(supported / total, 4) if total else 1.0,
        "supported_claims": supported,
        "total_claims": total,
        "claim_counts": counts,
        "unsupported_claims": unsupported,
    }


def _collect_text(obj: Any) -> str:
    """Flattens the string content of a nested structure (for identifier/ref lookup)."""
    out: List[str] = []
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            out.append(_collect_text(v))
    elif isinstance(obj, (list, tuple, set)):
        for v in obj:
            out.append(_collect_text(v))
    else:
        out.append(str(obj))
    return " ".join(out)


# --- Embedding-based relevancy (secondary proxy) -------------------------------
_EMBED_FN: Optional[Callable[[Sequence[str]], np.ndarray]] = None


def _default_embed_fn() -> Callable[[Sequence[str]], np.ndarray]:
    global _EMBED_FN
    if _EMBED_FN is None:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(EMBEDDING_MODEL_NAME)

        def _encode(texts: Sequence[str]) -> np.ndarray:
            return np.asarray(
                model.encode(list(texts), normalize_embeddings=True), dtype=np.float32
            )

        _EMBED_FN = _encode
    return _EMBED_FN


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def embedding_relevancy(
    text_a: str,
    text_b: str,
    *,
    embed_fn: Optional[Callable[[Sequence[str]], np.ndarray]] = None,
) -> float:
    """Cosine similarity between two texts under the supplied (or default) encoder."""
    if not str(text_a).strip() or not str(text_b).strip():
        return 0.0
    enc = embed_fn or _default_embed_fn()
    vecs = np.asarray(enc([text_a, text_b]), dtype=np.float32)
    return round(_cosine(vecs[0], vecs[1]), 4)


def answer_relevancy(
    question: str,
    answer: str,
    *,
    embed_fn: Optional[Callable[[Sequence[str]], np.ndarray]] = None,
) -> Dict[str, Any]:
    """Embedding cosine between the question and the answer (secondary proxy)."""
    score = embedding_relevancy(question, answer, embed_fn=embed_fn)
    return {
        "score": score,
        "proxy": f"embedding cosine ({EMBEDDING_MODEL_NAME}) - secondary proxy, not the RAGAS metric",
    }


def context_relevancy(
    question: str,
    retrieved_chunks: Sequence[Any],
    *,
    embed_fn: Optional[Callable[[Sequence[str]], np.ndarray]] = None,
) -> Dict[str, Any]:
    """Mean embedding cosine between the question and each retrieved chunk."""
    if not retrieved_chunks:
        return {
            "score": 0.0,
            "min": 0.0,
            "fraction_above_0_5": 0.0,
            "num_contexts": 0,
            "proxy": f"embedding cosine ({EMBEDDING_MODEL_NAME}) - secondary proxy, not the RAGAS metric",
        }
    index = build_context_index(retrieved_chunks)
    enc = embed_fn or _default_embed_fn()
    vecs = np.asarray(enc([question] + index["texts"]), dtype=np.float32)
    q_vec = vecs[0]
    sims = [_cosine(q_vec, v) for v in vecs[1:]]
    above = sum(1 for s in sims if s >= 0.5)
    return {
        "score": round(sum(sims) / len(sims), 4),
        "min": round(min(sims), 4),
        "fraction_above_0_5": round(above / len(sims), 4),
        "num_contexts": len(sims),
        "proxy": f"embedding cosine ({EMBEDDING_MODEL_NAME}) - secondary proxy, not the RAGAS metric",
    }


# --- Retrieval metrics from labelled questions --------------------------------
def precision_at_k(relevant: Iterable[str], retrieved: Sequence[str], k: int) -> float:
    top = list(retrieved)[:k]
    denom = min(k, len(list(retrieved)))
    if denom == 0:
        return 0.0
    rel = set(relevant)
    return len([c for c in top if c in rel]) / denom


def recall_at_k(relevant: Iterable[str], retrieved: Sequence[str], k: int) -> float:
    rel = set(relevant)
    if not rel:
        return 0.0
    top = set(list(retrieved)[:k])
    return len(rel & top) / len(rel)


def reciprocal_rank(relevant: Iterable[str], retrieved: Sequence[str]) -> float:
    rel = set(relevant)
    for rank, cid in enumerate(retrieved, 1):
        if cid in rel:
            return 1.0 / rank
    return 0.0


def aggregate_retrieval_metrics(cases: Sequence[Dict[str, Any]], k: int = 5) -> Dict[str, Any]:
    """
    Aggregates precision@k, recall@k and MRR over labelled cases.

    Each case: {"relevant": [chunk_id, ...], "retrieved": [chunk_id, ...],
                "code": "IS 456:2000", "question": "..."}.

    Reports the metrics grouped per code and for the multi-code set (all cases).
    """
    def _metrics(subset: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        n = len(subset)
        if n == 0:
            return {
                "num_queries": 0,
                "precision_at_k": 0.0,
                "recall_at_k": 0.0,
                "mrr": 0.0,
            }
        p = sum(precision_at_k(c["relevant"], c["retrieved"], k) for c in subset) / n
        r = sum(recall_at_k(c["relevant"], c["retrieved"], k) for c in subset) / n
        rr = sum(reciprocal_rank(c["relevant"], c["retrieved"]) for c in subset) / n
        return {
            "num_queries": n,
            "precision_at_k": round(p, 4),
            "recall_at_k": round(r, 4),
            "mrr": round(rr, 4),
        }

    per_code: Dict[str, Dict[str, Any]] = {}
    for case in cases:
        per_code.setdefault(case.get("code", "unknown"), []).append(case)

    return {
        "k": k,
        "per_code": {code: _metrics(subset) for code, subset in sorted(per_code.items())},
        "multi_code_set": _metrics(list(cases)),
    }
