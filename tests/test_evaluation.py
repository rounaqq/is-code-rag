"""
Unit tests for Step 9: Structural Design Evaluation & Benchmark.
Validates:
  1. Hand-calculation cross-checks.
  2. Full real-world design evaluation, self-consistency, and arithmetic re-checks from JSON tables.
  3. 2D CAD DXF generation and structural safety checks.
  4. Faithfulness, deterministic consistency, and valid IS 456 clause citations.
  5. RAGAS-style offline proxy metrics (rule-based; retrieval precision/recall/MRR + claim grounding).
  6. The independent engineer review blind package and attestation-record validation.
  7. Consolidated Step 9 master evaluation report integrity.
Does NOT read .env or call external networks.
"""

import json
from pathlib import Path
import pytest

from src.evaluation.run_design_eval import run_full_design_evaluation, REPORT_OUTPUT_FILE
from src.evaluation.run_sp16_eval import evaluate_sp16_benchmarks, REPORT_FILE as SP16_REPORT_FILE
from src.evaluation.run_step9_master_eval import (
    evaluate_faithfulness_and_citations,
    MASTER_REPORT_FILE,
)
from src.evaluation import rag_metrics
from src.evaluation.rag_metrics import (
    extract_claims,
    faithfulness,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    aggregate_retrieval_metrics,
)
from src.evaluation.run_rag_metrics_eval import build_report
from src.evaluation.run_independent_review import (
    build_blind_package,
    validate_review_record,
    evaluate_independent_review,
    RECORD_FILE,
    PILLAR_PENDING,
)


def test_step9_sp16_handbook_benchmarks():
    """Validates engine calculations against hand-calculation cross-checks."""
    sp16_summary = evaluate_sp16_benchmarks()

    assert sp16_summary["total_examples"] == 4
    assert sp16_summary["examples_passed"] == 4
    assert sp16_summary["pass_rate_pct"] == 100.0
    assert sp16_summary["all_congruent"] is True

    # Verify SP:16 report file generated on disk
    assert SP16_REPORT_FILE.exists()
    assert SP16_REPORT_FILE.stat().st_size > 500

    for rec in sp16_summary["results"]:
        assert rec["status"] == "PASSED"
        if rec["type"] == "Flexure":
            assert rec["ast_variance_pct"] <= 1.5
            assert rec["calculated"]["is_under_reinforced"] is True
        elif rec["type"] == "Shear":
            assert rec["spacing_variance_pct"] <= 2.0


def test_step9_full_design_evaluation_benchmark():
    """Step 9 benchmark evaluation across real-world design scenarios."""
    summary = run_full_design_evaluation()

    assert summary["total_scenarios"] >= 5
    assert summary["scenarios_passed"] == summary["total_scenarios"]
    assert summary["dxf_exports_verified"] == summary["total_scenarios"], "Not all scenarios produced valid DXF drawings"
    assert summary["arithmetic_recheck_from_json_tables_all_passed"] is True
    assert summary["disclaimer"] == "These results are not an independent validation. A structural engineer must review the designs."

    # Verify report was written to disk
    assert REPORT_OUTPUT_FILE.exists()
    assert REPORT_OUTPUT_FILE.stat().st_size > 500

    # Verify each scenario in detail
    for record in summary["scenario_reports"]:
        assert record["status"] == "PASSED"
        assert record["under_reinforced"] is True
        assert record["shear_safe"] is True
        assert record["cover_correct"] is True
        assert record["dxf_generated"] is True
        assert record["latency_ms"] < 2000.0  # Fast execution < 2 seconds


def test_step9_faithfulness_and_citation_audit():
    """Validates that narrative numbers match deterministic sizing with deterministic consistency and valid citations."""
    audit_summary = evaluate_faithfulness_and_citations()

    assert audit_summary["all_consistent"] is True
    assert audit_summary["all_disclaimers_present"] is True
    assert audit_summary["citation_validity_pct"] == 100.0

    for sc_audit in audit_summary["scenario_audits"]:
        assert sc_audit["status"] == "PASSED"
        assert sc_audit["consistent"] is True
        assert sc_audit["disclaimer_present"] is True
        assert len(sc_audit["discrepancies"]) == 0


def test_step9_master_evaluation_report_integrity():
    """Validates structure and success criteria of the consolidated Step 9 master evaluation report."""
    assert MASTER_REPORT_FILE.exists()
    assert MASTER_REPORT_FILE.stat().st_size > 1000

    with open(MASTER_REPORT_FILE, "r", encoding="utf-8") as f:
        master = json.load(f)

    assert master["step"] == 9
    assert master["overall_status"] == "PASSED"

    # Pillar 1: Retrieval Quality
    p1 = master["pillar_1_retrieval_quality"]
    assert p1["hit_at_3_pct"] == 100.0
    assert p1["hit_at_1_pct"] >= 80.0
    assert p1["mean_reciprocal_rank"] >= 0.85
    assert p1["status"] == "PASSED"

    # Pillar 2: Hand-calculation cross-checks
    p2 = master.get("pillar_2_hand_calculation_cross_checks") or master.get("pillar_2_sp16_handbook_benchmark")
    assert p2["all_congruent"] is True
    assert p2["pass_rate_pct"] == 100.0
    assert p2["status"] == "PASSED"

    # Pillar 3: Design Scenarios and CAD
    p3 = master["pillar_3_design_scenarios_and_cad"]
    assert p3["pass_rate_pct"] == 100.0
    assert p3["arithmetic_recheck_from_json_tables_all_passed"] is True
    assert p3["dxf_exports_verified"] == 5
    assert p3["status"] == "PASSED"

    # Pillar 4: Faithfulness & Citations
    p4 = master["pillar_4_faithfulness_and_citations"]
    assert p4["all_consistent"] is True
    assert p4["all_disclaimers_present"] is True
    assert p4["citation_validity_pct"] == 100.0
    assert p4["status"] == "PASSED"

    # Pillar 5: RAGAS-style offline proxy metrics (rule-based, not the RAGAS library)
    p5 = master["pillar_5_ragas_style_proxy_metrics"]
    assert "RAGAS library" in p5["framing"]
    assert "RAGAS-compatible" not in json.dumps(p5)
    assert "RAGAS score" not in json.dumps(p5)
    assert p5["retrieval_metrics"]["multi_code_set"]["recall_at_k"] >= 0.9
    assert p5["is_compliance_accuracy"]["status"] == "PENDING"
    assert p5["is_compliance_accuracy"]["value"] is None
    assert p5["status"] == "PASSED"

    # Pillar 6: Independent engineer review - never counted as a pass
    p6 = master["pillar_6_independent_engineer_review"]
    assert p6["counts_toward_pass"] is False
    assert "PASSED" not in p6["status"].upper()
    assert "APPROVED" not in p6["status"].upper()
    if not p6["record_present"]:
        assert p6["status"] == PILLAR_PENDING


def test_rag_metrics_claim_extraction():
    """Every number, identifier and clause reference is extracted as a claim."""
    claims = extract_claims("Per Cl. 26.5.1.1(a), M25 concrete and Fe500 steel, IS 456:2000 Table 16; span 4.5 m.")
    types = {c["type"] for c in claims}
    assert types == {"clause_ref", "identifier", "number"}
    values = [c["value"] for c in claims]
    assert any("26.5.1.1" in v for v in values)
    assert any(v.lower().startswith("m25") for v in values)
    assert "4.5" in values


def test_rag_metrics_clause_faithfulness_grounds_against_chunks():
    """Clause-mode: every claim must appear in the retrieved chunks."""
    chunks = [{
        "citation": "IS 456:2000 Cl. 26.5.1.1(a)",
        "title": "Minimum tension reinforcement",
        "text": "The minimum tension steel for M25 concrete shall satisfy the limits given herein.",
    }]
    grounded = faithfulness("Cl. 26.5.1.1(a) requires minimum tension steel for M25 concrete.", chunks, mode="clause")
    assert grounded["score"] == 1.0
    assert grounded["unsupported_claims"] == []

    ungrounded = faithfulness("See Cl. 99.9.9 for M99 concrete.", chunks, mode="clause")
    assert ungrounded["score"] == 0.0
    assert len(ungrounded["unsupported_claims"]) == 2


def test_rag_metrics_design_numbers_need_not_be_in_chunks():
    """Design-mode: numbers must match the calculator output, not the retrieved chunks."""
    sizing = {"section_dimensions": {"b": 300.0, "D": 450.0}, "factored_moment_kNm": 120.5}
    # Deliberately no retrieved chunks: the numbers must still be supported by the calculator.
    res = faithfulness("Section 300 x 450 mm, Mu = 120.5 kNm, per Cl. 26.5.1.1.", [], mode="design",
                       calculator_output=sizing)
    assert all(c["type"] != "number" for c in res["unsupported_claims"])
    assert any(c["type"] == "clause_ref" for c in res["unsupported_claims"])

    # Declared standard constants (unit weight, load factor) are accepted in design mode.
    declared = faithfulness("Unit weight 25 kN/m3 and load factor 1.5.", [], mode="design",
                            calculator_output={}, declared_constants=[25.0, 1.5])
    assert declared["score"] == 1.0


def test_rag_metrics_retrieval_metrics():
    """precision@k, recall@k and MRR computed from labelled relevant ids."""
    retrieved = ["A", "B", "C", "D", "E"]
    assert precision_at_k(["A"], retrieved, 5) == pytest.approx(0.2)
    assert recall_at_k(["A", "Z"], retrieved, 5) == pytest.approx(0.5)
    assert reciprocal_rank(["C"], retrieved) == pytest.approx(1.0 / 3.0)
    assert reciprocal_rank(["Z"], retrieved) == 0.0


def test_rag_metrics_aggregate_per_code_and_multi_code():
    """Retrieval metrics are reported per code and for the multi-code set."""
    cases = [
        {"relevant": ["IS456-1"], "retrieved": ["IS456-1", "x"], "code": "IS 456:2000"},
        {"relevant": ["IS875P2-1"], "retrieved": ["y", "IS875P2-1"], "code": "IS 875 (Part 2):1987"},
    ]
    agg = aggregate_retrieval_metrics(cases, k=2)
    assert set(agg["per_code"].keys()) == {"IS 456:2000", "IS 875 (Part 2):1987"}
    assert agg["multi_code_set"]["num_queries"] == 2
    assert agg["multi_code_set"]["recall_at_k"] == 1.0
    assert agg["multi_code_set"]["mrr"] == pytest.approx(0.75)


def test_rag_metrics_report_is_framing_compliant_and_pending_compliance():
    """The report labels the metrics as rule-based proxies and leaves compliance PENDING."""
    retrieval = aggregate_retrieval_metrics(
        [{"relevant": ["a"], "retrieved": ["a"], "code": "IS 456:2000"}], k=5
    )
    report = build_report(
        retrieval,
        {"mean_score": 1.0},
        {"templated": {"mean_score": 0.95, "note": "partly circular"},
         "model_written": {"status": "UNAVAILABLE - no endpoint"}},
        {"context_relevancy": {"mean_score": 0.5}, "answer_relevancy": {"mean_score": 0.6}, "per_scenario": []},
    )
    blob = json.dumps(report)
    assert "RAGAS-compatible" not in blob
    assert "RAGAS score" not in blob
    assert "NOT the RAGAS library" in report["framing"]
    assert report["is_compliance_accuracy"]["status"] == "PENDING"
    assert report["is_compliance_accuracy"]["value"] is None


def test_independent_review_blind_package_has_no_expected_answers():
    """The blind package ships inputs and designs only - never the author's expected answers."""
    package = build_blind_package(write=False)
    assert len(package["designs"]) >= 5
    assert package["assumption_list"]
    assert package["unsourced_items"]
    for design in package["designs"]:
        assert "expected" not in json.dumps(design).lower()
        assert "governing_clauses" not in json.dumps(design)


def _valid_record():
    return {
        "author_name": "A. Author",
        "reviewer_name": "B. Reviewer",
        "role": "Chartered Structural Engineer",
        "registration_number": "REG-12345",
        "date": "2026-01-15",
        "scope": "Independent check of beam designs SCEN-01..SCEN-05",
        "designs": [
            {"scenario_id": "SCEN-01", "outcome": "accepted", "comments": "Checks verified."},
        ],
    }


def test_independent_review_record_validation():
    """A complete, independent record is valid; reviewer==author is rejected."""
    assert validate_review_record(_valid_record(), expected_scenario_ids=["SCEN-01"])["valid"] is True

    same = dict(_valid_record(), reviewer_name="  a.   AUTHOR ")
    res = validate_review_record(same)
    assert res["valid"] is False
    assert any("equals the author" in r for r in res["reasons"])

    missing = {k: v for k, v in _valid_record().items() if k != "registration_number"}
    assert validate_review_record(missing)["valid"] is False

    bad_outcome = dict(_valid_record(), designs=[
        {"scenario_id": "SCEN-01", "outcome": "approved", "comments": ""}
    ])
    assert validate_review_record(bad_outcome)["valid"] is False

    incomplete = validate_review_record(_valid_record(), expected_scenario_ids=["SCEN-01", "SCEN-02"])
    assert incomplete["valid"] is False


def test_independent_review_pillar_is_never_counted_as_a_pass():
    """The pillar stays PENDING without a genuine record and never counts toward master pass."""
    pillar = evaluate_independent_review()
    assert pillar["counts_toward_pass"] is False
    assert "PASSED" not in pillar["status"].upper()
    assert "APPROVED" not in pillar["status"].upper()
    # Scripts and tests never create a record: the reported presence matches the filesystem.
    assert pillar["record_present"] == RECORD_FILE.exists()
    if not pillar["record_present"]:
        assert pillar["status"] == PILLAR_PENDING
