"""
Unit tests for Step 9: Structural Design Evaluation & Benchmark.
Validates:
  1. Hand-calculation cross-checks.
  2. Full real-world design evaluation, self-consistency, and arithmetic re-checks from JSON tables.
  3. 2D CAD DXF generation and structural safety checks.
  4. Faithfulness, deterministic consistency, and valid IS 456 clause citations.
  5. Consolidated Step 9 master evaluation report integrity.
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
