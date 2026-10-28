"""
Step 9 (extension): RAGAS-style Offline Proxy Metrics Report.

Produces `data/eval/rag_metrics_report.json` containing:
  * Retrieval figures (precision@k, recall@k, MRR) computed from the labelled
    benchmark questions - reported per code and for the multi-code set.
  * Faithfulness (rule-based claim grounding), reported separately for
    templated (code-written) answers and model-written answers.
  * Context relevancy and answer relevancy as secondary embedding proxies.
  * IS-compliance accuracy, recorded as PENDING (needs an independent source).

FRAMING: everything here is a rule-based proxy for the RAGAS metric
definitions, NOT the RAGAS library. No `ragas`/`trulens` package is installed
or imported and no network access is used.
"""

import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Callable, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.evaluation import rag_metrics
from src.generation.beam_sizing import design_and_validate_beam
from src.generation.design_assistant import generate_design_explanation

QUESTIONS_FILE = Path("data/eval/questions.json")
SCENARIOS_FILE = Path("data/eval/structural_design_scenarios.json")
CHUNKS_FILE = Path("data/processed/chunks.jsonl")
REPORT_FILE = Path("data/eval/rag_metrics_report.json")

TOP_K = 5
DESIGN_CONTEXT_K = 10

FRAMING = (
    "RAGAS-style offline proxy metrics: these are rule-based proxies for the RAGAS metric "
    "definitions (faithfulness, answer relevancy, context relevancy), NOT the RAGAS library. "
    "No `ragas`/`trulens` package is installed or imported and no network access is used. "
    "Claim grounding is rule-based and relevancy is an embedding proxy."
)

CLAUSE_ANSWER_NOTE = (
    "Clause-answer faithfulness checks that every number, identifier and clause reference in the "
    "answer appears in the retrieved chunks. The pipeline is retrieval-only (no generative clause "
    "answering), so the answer evaluated here is extractive (the retrieved chunk text itself) and is "
    "grounded by construction - this figure is reported for completeness and is partly circular."
)

TEMPLATED_NOTE = (
    "Templated (code-written) faithfulness: the same deterministic code that produced the design "
    "numbers also grounds them, so this figure is PARTLY CIRCULAR and is expected to be high."
)

IS_COMPLIANCE_NOTE = (
    "IS-compliance accuracy requires a source independent of this repository (a published worked "
    "example or a licensed engineer's verdict). It is intentionally left PENDING rather than scored."
)

# Declared standard constants that legitimately appear in the templated explanation but are not
# numeric leaves of the calculator output (unit weight, load factor, Ld/3 divisor).
DECLARED_CONSTANTS = [25.0, 1.5, 3.0]


def _code_from_chunk_id(chunk_id: str) -> str:
    cid = (chunk_id or "").upper()
    if cid.startswith("IS456"):
        return "IS 456:2000"
    if cid.startswith("IS13920"):
        return "IS 13920:2016"
    if cid.startswith("IS1893"):
        return "IS 1893 (Part 1):2016"
    if cid.startswith("IS875"):
        return "IS 875 (Part 2):1987"
    if cid.startswith("IS800"):
        return "IS 800:2007"
    return "unknown"


def _load_chunk_index(path: Path = CHUNKS_FILE) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}
    if not path.exists():
        return index
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                chunk = json.loads(line.strip())
                index[chunk["chunk_id"]] = {
                    "chunk_id": chunk["chunk_id"],
                    "citation": chunk.get("citation", chunk["chunk_id"]),
                    "title": chunk.get("title", ""),
                    "text": chunk.get("text", ""),
                }
    return index


def _chunks_for_ids(ids: List[str], index: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for cid in ids:
        rec = index.get(cid)
        if rec:
            out.append(rec)
        else:
            out.append({"chunk_id": cid, "citation": cid, "title": "", "text": ""})
    return out


def _retrieve(query: str, k: int = TOP_K) -> List[Dict[str, Any]]:
    """Retrieves top-k chunks via the cross-encoder reranker (same retriever as Pillar 1)."""
    from src.retrieval.rerank import search as rerank_search

    return rerank_search(query, k=k, top_n_hybrid=k)


def evaluate_clause_answer_faithfulness(
    retrievals: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """
    Clause-answer faithfulness over extractive answers.
    `retrievals` maps question -> list of retrieved chunk dicts (with text/title/citation).
    """
    per_question = []
    scores = []
    for question, chunks in retrievals.items():
        chunks = chunks or []
        answer = "\n".join((c.get("text") or c.get("citation") or "") for c in chunks[:3])
        res = rag_metrics.faithfulness(answer, chunks, mode="clause")
        scores.append(res["score"])
        per_question.append({
            "question": question,
            "answer_type": "extractive (retrieved chunk text)",
            "score": res["score"],
            "supported_claims": res["supported_claims"],
            "total_claims": res["total_claims"],
            "unsupported_claims": res["unsupported_claims"],
        })
    mean = round(sum(scores) / len(scores), 4) if scores else 1.0
    return {
        "mode": "clause",
        "answer_type": "extractive (retrieval-only pipeline)",
        "mean_score": mean,
        "num_questions": len(per_question),
        "note": CLAUSE_ANSWER_NOTE,
        "per_question": per_question,
    }


def evaluate_design_faithfulness(
    scenarios: List[Dict[str, Any]],
    chunk_index: Dict[str, Dict[str, Any]],
    *,
    use_model_llm: bool = True,
) -> Dict[str, Any]:
    """
    Faithfulness for design explanations.

    Templated answers are always produced (deterministic fallback generator).
    Model-written answers are attempted only when an LLM endpoint is reachable;
    otherwise the model-written pillar is reported as UNAVAILABLE.
    """
    templated_records = []
    templated_scores = []

    model_llm, model_state = _make_probe_llm() if use_model_llm else (None, {"ok": False, "error": "disabled"})
    model_records = []
    model_scores = []

    # Probe the LLM once: nothing is fabricated if the endpoint is unreachable.
    if model_llm is not None:
        try:
            model_llm("Reply with the single word OK.", "You are a connectivity probe.")
        except Exception:
            pass

    for sc in scenarios:
        inp = sc["inputs"]
        res = design_and_validate_beam(
            span_m=inp["span_m"],
            dead_load_kN_per_m=inp["dead_load_kN_per_m"],
            live_load_kN_per_m=inp["live_load_kN_per_m"],
            fck=inp["fck"],
            fy=inp["fy"],
            exposure=inp["exposure"],
        )
        sizing = res["sizing"]
        query = (
            f"Design a simply supported RC beam: span {inp['span_m']} m, "
            f"dead load {inp['dead_load_kN_per_m']} kN/m, live load {inp['live_load_kN_per_m']} kN/m, "
            f"M{int(inp['fck'])}/Fe{int(inp['fy'])}, {inp['exposure']} exposure."
        )

        retrieved = _retrieve(query, k=DESIGN_CONTEXT_K)
        contexts = _chunks_for_ids([c["chunk_id"] for c in retrieved], chunk_index)

        # Templated (code-written) answer.
        templated_answer = generate_design_explanation(
            user_query=query, sizing_result={"sizing": sizing, "status": "ok"}, llm=_always_fail_llm
        )
        t_res = rag_metrics.faithfulness(
            templated_answer,
            contexts,
            mode="design",
            calculator_output=sizing,
            declared_constants=DECLARED_CONSTANTS,
        )
        templated_scores.append(t_res["score"])
        templated_records.append({
            "scenario_id": sc["scenario_id"],
            "score": t_res["score"],
            "supported_claims": t_res["supported_claims"],
            "total_claims": t_res["total_claims"],
            "unsupported_claims": t_res["unsupported_claims"],
            "num_contexts": len(contexts),
        })

        # Model-written answer (only if the LLM is reachable).
        if model_llm is not None and model_state["ok"]:
            model_answer = generate_design_explanation(
                user_query=query, sizing_result={"sizing": sizing, "status": "ok"}, llm=model_llm
            )
            m_res = rag_metrics.faithfulness(
                model_answer,
                contexts,
                mode="design",
                calculator_output=sizing,
                declared_constants=DECLARED_CONSTANTS,
            )
            model_scores.append(m_res["score"])
            model_records.append({
                "scenario_id": sc["scenario_id"],
                "score": m_res["score"],
                "supported_claims": m_res["supported_claims"],
                "total_claims": m_res["total_claims"],
                "unsupported_claims": m_res["unsupported_claims"],
                "num_contexts": len(contexts),
            })

    templated_mean = round(sum(templated_scores) / len(templated_scores), 4) if templated_scores else 1.0
    templated_bundle = {
        "answer_type": "templated (code-written)",
        "mean_score": templated_mean,
        "num_scenarios": len(templated_records),
        "note": TEMPLATED_NOTE,
        "per_scenario": templated_records,
    }

    if model_records:
        model_bundle = {
            "answer_type": "model-written",
            "mean_score": round(sum(model_scores) / len(model_scores), 4),
            "num_scenarios": len(model_records),
            "per_scenario": model_records,
        }
    else:
        reason = model_state.get("error") or "no LLM endpoint reachable"
        model_bundle = {
            "answer_type": "model-written",
            "status": f"UNAVAILABLE - {reason}",
            "mean_score": None,
            "num_scenarios": 0,
            "per_scenario": [],
        }

    return {"templated": templated_bundle, "model_written": model_bundle}


def _always_fail_llm(*_args: Any, **_kwargs: Any) -> str:
    """Forces the deterministic templated fallback generator."""
    raise RuntimeError("forced templated fallback")


def _make_probe_llm(timeout: Optional[float] = None):
    """
    Builds an LLM callable that records success/failure. Used only to determine
    whether a model-written answer is available; nothing is fabricated on failure.
    """
    from src.generation.llm_client import OllamaClient

    if timeout is None:
        try:
            timeout = float(os.getenv("EVAL_LLM_TIMEOUT", "8"))
        except ValueError:
            timeout = 8.0

    state: Dict[str, Any] = {"ok": False, "error": None}
    client = OllamaClient(timeout=timeout)

    def _llm(prompt: str, system_prompt: Optional[str] = None, **_kwargs: Any) -> str:
        try:
            out = client.generate(prompt=prompt, system_prompt=system_prompt)
            state["ok"] = True
            return out
        except Exception as exc:  # network / endpoint unavailable
            state["error"] = f"LLM endpoint unavailable ({type(exc).__name__})"
            raise

    return _llm, state


def evaluate_context_and_answer_relevancy(
    scenarios: List[Dict[str, Any]],
    chunk_index: Dict[str, Dict[str, Any]],
    *,
    embed_fn: Optional[Callable] = None,
) -> Dict[str, Any]:
    """Embedding-based context relevancy and answer relevancy (secondary proxies)."""
    ctx_scores = []
    ans_scores = []
    per_scenario = []

    for sc in scenarios:
        inp = sc["inputs"]
        res = design_and_validate_beam(
            span_m=inp["span_m"],
            dead_load_kN_per_m=inp["dead_load_kN_per_m"],
            live_load_kN_per_m=inp["live_load_kN_per_m"],
            fck=inp["fck"],
            fy=inp["fy"],
            exposure=inp["exposure"],
        )
        sizing = res["sizing"]
        query = (
            f"Design a simply supported RC beam: span {inp['span_m']} m, "
            f"dead load {inp['dead_load_kN_per_m']} kN/m, live load {inp['live_load_kN_per_m']} kN/m, "
            f"M{int(inp['fck'])}/Fe{int(inp['fy'])}, {inp['exposure']} exposure."
        )
        retrieved = _retrieve(query, k=DESIGN_CONTEXT_K)
        contexts = _chunks_for_ids([c["chunk_id"] for c in retrieved], chunk_index)

        c_res = rag_metrics.context_relevancy(query, contexts, embed_fn=embed_fn)
        answer = generate_design_explanation(
            user_query=query, sizing_result={"sizing": sizing, "status": "ok"}, llm=_always_fail_llm
        )
        a_res = rag_metrics.answer_relevancy(query, answer, embed_fn=embed_fn)

        ctx_scores.append(c_res["score"])
        ans_scores.append(a_res["score"])
        per_scenario.append({
            "scenario_id": sc["scenario_id"],
            "context_relevancy": c_res["score"],
            "answer_relevancy": a_res["score"],
        })

    n = len(per_scenario) or 1
    return {
        "context_relevancy": {
            "mean_score": round(sum(ctx_scores) / n, 4) if per_scenario else 0.0,
            "proxy": f"embedding cosine ({rag_metrics.EMBEDDING_MODEL_NAME}) - secondary proxy",
        },
        "answer_relevancy": {
            "mean_score": round(sum(ans_scores) / n, 4) if per_scenario else 0.0,
            "proxy": f"embedding cosine ({rag_metrics.EMBEDDING_MODEL_NAME}) - secondary proxy",
        },
        "per_scenario": per_scenario,
    }


def build_report(
    retrieval_metrics: Dict[str, Any],
    clause_faithfulness: Dict[str, Any],
    design_faithfulness: Dict[str, Any],
    relevancy: Dict[str, Any],
) -> Dict[str, Any]:
    """Assembles the RAGAS-style offline proxy metrics report (pure function)."""
    return {
        "evaluation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "step": 9,
        "title": "Step 9 (extension): RAGAS-style Offline Proxy Metrics",
        "framing": FRAMING,
        "retrieval_metrics": retrieval_metrics,
        "faithfulness": {
            "clause_answers": clause_faithfulness,
            "design_explanations": design_faithfulness,
        },
        "context_relevancy": relevancy.get("context_relevancy"),
        "answer_relevancy": relevancy.get("answer_relevancy"),
        "relevancy_per_scenario": relevancy.get("per_scenario", []),
        "is_compliance_accuracy": {
            "status": "PENDING",
            "value": None,
            "reason": IS_COMPLIANCE_NOTE,
        },
        "disclaimer": (
            "These are rule-based offline proxies, not the RAGAS library and not an independent "
            "validation. A structural engineer must review the designs."
        ),
    }


def run_rag_metrics_eval(*, write: bool = True) -> Dict[str, Any]:
    """Runs the full RAGAS-style offline proxy metrics evaluation."""
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        questions = json.load(f)
    with open(SCENARIOS_FILE, "r", encoding="utf-8") as f:
        scenarios = json.load(f)

    chunk_index = _load_chunk_index()

    # 1. Retrieval metrics + clause-answer contexts.
    cases = []
    retrievals: Dict[str, List[Dict[str, Any]]] = {}
    for item in questions:
        q = item["question"]
        expected = item["expected_chunk_id"]
        results = _retrieve(q, k=TOP_K)
        retrieved_ids = [r["chunk_id"] for r in results]
        cases.append({
            "question": q,
            "relevant": [expected],
            "retrieved": retrieved_ids,
            "code": _code_from_chunk_id(expected),
        })
        retrievals[q] = _chunks_for_ids(retrieved_ids, chunk_index)

    retrieval_metrics = rag_metrics.aggregate_retrieval_metrics(cases, k=TOP_K)

    # 2. Faithfulness.
    clause_faithfulness = evaluate_clause_answer_faithfulness(retrievals)
    design_faithfulness = evaluate_design_faithfulness(scenarios, chunk_index)

    # 3. Relevancy proxies.
    relevancy = evaluate_context_and_answer_relevancy(scenarios, chunk_index)

    report = build_report(retrieval_metrics, clause_faithfulness, design_faithfulness, relevancy)

    if write:
        REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

    return report


def main() -> None:
    report = run_rag_metrics_eval()
    mm = report["retrieval_metrics"]["multi_code_set"]
    print("=" * 100)
    print("STEP 9 (EXTENSION): RAGAS-STYLE OFFLINE PROXY METRICS")
    print("=" * 100)
    print(f"Retrieval (multi-code set, k={report['retrieval_metrics']['k']}): "
          f"precision@{report['retrieval_metrics']['k']}={mm['precision_at_k']}, "
          f"recall@{report['retrieval_metrics']['k']}={mm['recall_at_k']}, MRR={mm['mrr']}")
    print(f"Faithfulness - templated (code-written): "
          f"{report['faithfulness']['design_explanations']['templated']['mean_score']} (partly circular)")
    print(f"Faithfulness - model-written: "
          f"{report['faithfulness']['design_explanations']['model_written'].get('status', report['faithfulness']['design_explanations']['model_written']['mean_score'])}")
    print(f"IS-compliance accuracy: {report['is_compliance_accuracy']['status']}")
    print(f"Report: {REPORT_FILE}")
    print("=" * 100)


if __name__ == "__main__":
    main()
