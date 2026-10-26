"""
Step 9: Master End-to-End IS 456 Evaluation & Validation Framework.
Unifies all four pillars of the Step 9 evaluation specification:
  Part 1: RAG & Hybrid Retrieval Benchmark (19 questions, Hit@1, Hit@3, MRR).
  Part 2: Hand-calculation cross-checks (written by the author of this repository, not published values).
  Part 3: End-to-End Real-World Structural Design Scenarios (5 building types, self-consistency,
          arithmetic re-checks from JSON tables, under-reinforced limit, 2D CAD DXF export).
  Part 4: Faithfulness & Citation Audit (deterministic consistency verification,
          chunk citation validation, engineering disclaimers).
Does NOT import, read, print, or quote .env or any secret keys.
"""

import json
import math
from pathlib import Path
import sys
import time
from typing import Dict, Any, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.retrieval.rerank import get_reranker, search as rerank_search
from src.evaluation.run_sp16_eval import evaluate_sp16_benchmarks
from src.evaluation.run_design_eval import run_full_design_evaluation
from src.generation.beam_sizing import design_and_validate_beam
from src.generation.design_assistant import (
    generate_design_explanation,
    verify_explanation_consistency,
    BASE_DISCLAIMER,
)

QUESTIONS_FILE = Path("data/eval/questions.json")
SP16_FILE = Path("data/eval/sp16_worked_examples.json")
SCENARIOS_FILE = Path("data/eval/structural_design_scenarios.json")
CHUNKS_FILE = Path("data/processed/chunks.jsonl")
MASTER_REPORT_FILE = Path("data/eval/step9_master_evaluation_report.json")


def evaluate_retrieval_quality() -> Dict[str, Any]:
    """
    Part 1: Evaluates retrieval quality metrics across the 19 benchmark questions.
    Computes Hit@1, Hit@3, and Mean Reciprocal Rank (MRR).
    """
    if not QUESTIONS_FILE.exists():
        raise FileNotFoundError(f"Questions file not found at {QUESTIONS_FILE}")

    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        questions = json.load(f)

    total_q = len(questions)
    hit_1 = 0
    hit_3 = 0
    reciprocal_ranks = []
    query_details = []
    latencies = []

    # Pre-warm reranker model
    reranker = get_reranker()

    print("\n" + "-" * 105)
    print("PART 1: RETRIEVAL & RAG QUALITY BENCHMARK (19 QUESTIONS)")
    print("-" * 105)

    for i, item in enumerate(questions, 1):
        q = item["question"]
        expected = item["expected_chunk_id"]

        t0 = time.perf_counter()
        results = reranker.search(q, k=5, top_n_hybrid=5)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(dt_ms)

        rank = next((idx for idx, r in enumerate(results, 1) if r["chunk_id"] == expected), None)

        is_hit_1 = (rank == 1)
        is_hit_3 = (rank is not None and rank <= 3)

        if is_hit_1:
            hit_1 += 1
        if is_hit_3:
            hit_3 += 1

        rr = 1.0 / rank if rank else 0.0
        reciprocal_ranks.append(rr)

        query_details.append({
            "index": i,
            "question": q,
            "expected_chunk_id": expected,
            "rerank_rank": rank,
            "hit_at_1": is_hit_1,
            "hit_at_3": is_hit_3,
            "reciprocal_rank": round(rr, 4),
            "latency_ms": round(dt_ms, 1),
            "top_retrieved": [
                {"rank": idx, "chunk_id": r["chunk_id"], "score": round(float(r["score"]), 4)}
                for idx, r in enumerate(results[:3], 1)
            ],
        })

    mrr = sum(reciprocal_ranks) / total_q if total_q else 0.0
    avg_latency = sum(latencies) / total_q if total_q else 0.0
    hit_1_pct = (hit_1 / total_q) * 100.0 if total_q else 0.0
    hit_3_pct = (hit_3 / total_q) * 100.0 if total_q else 0.0

    print(f"Total Questions Evaluated:  {total_q}")
    print(f"Hit@1:                      {hit_1}/{total_q} ({hit_1_pct:.1f}%)")
    print(f"Hit@3:                      {hit_3}/{total_q} ({hit_3_pct:.1f}%)")
    print(f"Mean Reciprocal Rank (MRR): {mrr:.4f}")
    print(f"Average Query Latency:      {avg_latency:.1f} ms")

    return {
        "total_questions": total_q,
        "hit_at_1_count": hit_1,
        "hit_at_1_pct": round(hit_1_pct, 2),
        "hit_at_3_count": hit_3,
        "hit_at_3_pct": round(hit_3_pct, 2),
        "mean_reciprocal_rank": round(mrr, 4),
        "avg_retrieval_latency_ms": round(avg_latency, 2),
        "questions": query_details,
    }


def evaluate_faithfulness_and_citations() -> Dict[str, Any]:
    """
    Part 4: Evaluates faithfulness, numerical consistency,
    and validity of IS 456 citations across the 5 design scenarios.
    """
    if not SCENARIOS_FILE.exists():
        raise FileNotFoundError(f"Scenarios file not found at {SCENARIOS_FILE}")
    if not CHUNKS_FILE.exists():
        raise FileNotFoundError(f"Chunks file not found at {CHUNKS_FILE}")

    # Load verified chunk IDs
    valid_chunk_ids = set()
    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                chunk = json.loads(line.strip())
                valid_chunk_ids.add(chunk["chunk_id"])

    with open(SCENARIOS_FILE, "r", encoding="utf-8") as f:
        scenarios = json.load(f)

    print("\n" + "-" * 105)
    print("PART 4: FAITHFULNESS & CITATION AUDIT (5 SCENARIOS)")
    print("-" * 105)

    scenario_audits = []
    all_consistent = True
    all_disclaimers_present = True
    total_citations_checked = 0
    valid_citations_count = 0

    for sc in scenarios:
        sc_id = sc["scenario_id"]
        inp = sc["inputs"]

        # Run deterministic sizing
        res = design_and_validate_beam(
            span_m=inp["span_m"],
            dead_load_kN_per_m=inp["dead_load_kN_per_m"],
            live_load_kN_per_m=inp["live_load_kN_per_m"],
            fck=inp["fck"],
            fy=inp["fy"],
            exposure=inp["exposure"],
        )
        sizing = res["sizing"]

        # Generate engineering explanation (fallback deterministic generator)
        explanation = generate_design_explanation(
            user_query=f"Size a beam with span {inp['span_m']}m under DL {inp['dead_load_kN_per_m']} and LL {inp['live_load_kN_per_m']}",
            sizing_result={"sizing": sizing, "status": "ok"},
            llm=None,
        )

        # Audit numerical consistency: b, D, bar count, bar dia, stirrup spacing
        consistency = verify_explanation_consistency(explanation, {"sizing": sizing})
        if not consistency["consistent"]:
            all_consistent = False

        # Audit disclaimer presence
        disclaimer_present = BASE_DISCLAIMER in explanation
        if not disclaimer_present:
            all_disclaimers_present = False

        # Audit citations
        citations = sizing.get("is456_citations", [])
        sc_valid_citations = []
        for c in citations:
            total_citations_checked += 1
            # Check if citation refers to valid chunk ID or standard clause prefix
            c_clean = c.strip()
            is_valid = (c_clean in valid_chunk_ids) or c_clean.startswith("IS 456") or c_clean.startswith("IS456")
            if is_valid:
                valid_citations_count += 1
            sc_valid_citations.append({"citation": c_clean, "valid": is_valid})

        audit_rec = {
            "scenario_id": sc_id,
            "name": sc["name"],
            "consistent": consistency["consistent"],
            "discrepancies": consistency["discrepancies"],
            "disclaimer_present": disclaimer_present,
            "citations_checked": len(citations),
            "citations": sc_valid_citations,
            "status": "PASSED" if (consistency["consistent"] and disclaimer_present) else "FAILED",
        }
        scenario_audits.append(audit_rec)

        print(f"[{sc_id}] {sc['name']}: Consistent = {consistency['consistent']} | Disclaimer = {disclaimer_present} | Citations = {len(citations)} valid")

    citation_validity_pct = (valid_citations_count / total_citations_checked * 100.0) if total_citations_checked else 100.0

    print(f"\nAll Numerical Values Sourced Deterministically from Sizing Engine: {all_consistent}")
    print(f"Mandatory Engineering Disclaimer Present in All Reports:            {all_disclaimers_present}")
    print(f"Valid Clause Citations:                                             {valid_citations_count}/{total_citations_checked} ({citation_validity_pct:.1f}%)")

    return {
        "all_consistent": all_consistent,
        "all_disclaimers_present": all_disclaimers_present,
        "total_citations_checked": total_citations_checked,
        "valid_citations_count": valid_citations_count,
        "citation_validity_pct": round(citation_validity_pct, 2),
        "scenario_audits": scenario_audits,
    }


def run_step9_master_evaluation() -> Dict[str, Any]:
    """
    Executes the complete, unified Step 9 evaluation benchmark.
    Consolidates Parts 1-4 and saves a report to disk.
    """
    t_start = time.perf_counter()

    print("=" * 105)
    print("STEP 9: MASTER IS 456 STRUCTURAL RAG & 2D CAD EVALUATION FRAMEWORK")
    print("=" * 105)

    # Part 1: Retrieval & RAG Benchmark
    retrieval_report = evaluate_retrieval_quality()

    # Part 2: Hand-calculation cross-checks (written by author of this repository, not published values)
    print("\n" + "-" * 105)
    print("PART 2: HAND-CALCULATION CROSS-CHECKS (WRITTEN BY THE AUTHOR OF THIS REPOSITORY, NOT PUBLISHED VALUES)")
    print("-" * 105)
    sp16_report = evaluate_sp16_benchmarks()

    # Part 3: Real-World Design Scenarios
    print("\n" + "-" * 105)
    print("PART 3: REAL-WORLD DESIGN SCENARIOS & CAD DXF EXPORT BENCHMARK")
    print("-" * 105)
    design_report = run_full_design_evaluation()

    # Part 4: Faithfulness & Citation Audit
    faithfulness_report = evaluate_faithfulness_and_citations()

    total_duration_s = time.perf_counter() - t_start

    # Consolidated Master Status
    master_passed = (
        retrieval_report["hit_at_3_pct"] >= 95.0
        and sp16_report["all_congruent"]
        and design_report["scenario_pass_rate_pct"] == 100.0
        and design_report["arithmetic_recheck_from_json_tables_all_passed"]
        and faithfulness_report["all_consistent"]
        and faithfulness_report["all_disclaimers_present"]
    )

    master_summary = {
        "evaluation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "step": 9,
        "title": "Step 9 Master Evaluation Report: IS 456 Structural RAG & 2D CAD Generation",
        "overall_status": "PASSED" if master_passed else "FAILED",
        "total_duration_seconds": round(total_duration_s, 2),
        "disclaimer": "These results are not an independent validation. A structural engineer must review the designs.",
        "pillar_1_retrieval_quality": {
            "total_questions": retrieval_report["total_questions"],
            "hit_at_1_pct": retrieval_report["hit_at_1_pct"],
            "hit_at_3_pct": retrieval_report["hit_at_3_pct"],
            "mean_reciprocal_rank": retrieval_report["mean_reciprocal_rank"],
            "avg_latency_ms": retrieval_report["avg_retrieval_latency_ms"],
            "status": "PASSED" if retrieval_report["hit_at_3_pct"] >= 95.0 else "FAILED",
        },
        "pillar_2_hand_calculation_cross_checks": {
            "source": sp16_report.get("source", "Hand-calculation cross-checks (written by the author of this repository, not published values)"),
            "total_examples": sp16_report["total_examples"],
            "examples_passed": sp16_report["examples_passed"],
            "pass_rate_pct": sp16_report["pass_rate_pct"],
            "all_congruent": sp16_report["all_congruent"],
            "status": "PASSED" if sp16_report["all_congruent"] else "FAILED",
        },
        # Backwards compatible key for existing tests
        "pillar_2_sp16_handbook_benchmark": {
            "handbook_source": "Hand-calculation cross-checks (written by the author of this repository, not published values)",
            "total_examples": sp16_report["total_examples"],
            "examples_passed": sp16_report["examples_passed"],
            "pass_rate_pct": sp16_report["pass_rate_pct"],
            "all_congruent": sp16_report["all_congruent"],
            "status": "PASSED" if sp16_report["all_congruent"] else "FAILED",
        },
        "pillar_3_design_scenarios_and_cad": {
            "total_scenarios": design_report["total_scenarios"],
            "scenarios_passed": design_report["scenarios_passed"],
            "pass_rate_pct": design_report["scenario_pass_rate_pct"],
            "dxf_exports_verified": design_report["dxf_exports_verified"],
            "arithmetic_recheck_from_json_tables_all_passed": design_report["arithmetic_recheck_from_json_tables_all_passed"],
            "avg_latency_ms": design_report["avg_latency_ms"],
            "status": "PASSED" if design_report["scenario_pass_rate_pct"] == 100.0 else "FAILED",
        },
        "pillar_4_faithfulness_and_citations": {
            "all_consistent": faithfulness_report["all_consistent"],
            "all_disclaimers_present": faithfulness_report["all_disclaimers_present"],
            "citation_validity_pct": faithfulness_report["citation_validity_pct"],
            "status": "PASSED" if faithfulness_report["all_consistent"] else "FAILED",
        },
        "detailed_reports": {
            "retrieval": retrieval_report,
            "sp16_handbook": sp16_report,
            "structural_design": design_report,
            "faithfulness": faithfulness_report,
        },
    }

    MASTER_REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MASTER_REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(master_summary, f, indent=2)

    print("\n" + "=" * 105)
    print("STEP 9 MASTER EVALUATION SUITE SUMMARY")
    print("=" * 105)
    print(f"Overall Step 9 Status:                {master_summary['overall_status']}")
    print(f"Pillar 1 - RAG Retrieval Quality:     Hit@1: {retrieval_report['hit_at_1_pct']}%, Hit@3: {retrieval_report['hit_at_3_pct']}%, MRR: {retrieval_report['mean_reciprocal_rank']}")
    print(f"Pillar 2 - Cross-Checks:              {sp16_report['examples_passed']}/{sp16_report['total_examples']} ({sp16_report['pass_rate_pct']}%) congruent with reference hand calculations")
    print(f"Pillar 3 - Real-World Scenarios:      {design_report['scenarios_passed']}/{design_report['total_scenarios']} ({design_report['scenario_pass_rate_pct']}%) passed, {design_report['dxf_exports_verified']} CAD DXFs verified")
    print(f"Pillar 4 - Faithfulness & Citations:  Numerically Sourced: {faithfulness_report['all_consistent']}, Citations: {faithfulness_report['citation_validity_pct']}% valid")
    print(f"Total Suite Execution Time:           {total_duration_s:.2f} seconds")
    print(f"Report Saved To:                      {MASTER_REPORT_FILE}")
    print("=" * 105)
    print(master_summary["disclaimer"])
    print("=" * 105)

    return master_summary


if __name__ == "__main__":
    run_step9_master_evaluation()
