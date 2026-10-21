"""
Unit tests for Step 9: Structural Design Evaluation & IS 456 Compliance Benchmark.
Validates 100% compliance accuracy, zero error rate, CAD DXF generation,
and time-savings metrics across real-world design scenarios.
Does NOT read .env or call external networks.
"""

from pathlib import Path
import pytest
from src.evaluation.run_design_eval import run_full_design_evaluation, REPORT_OUTPUT_FILE


def test_step9_full_design_evaluation_benchmark():
    """Step 9 benchmark achieves 100% IS 456 compliance and 0% error rate."""
    summary = run_full_design_evaluation()

    assert summary["total_scenarios"] >= 5
    assert summary["scenario_pass_rate_pct"] == 100.0, f"Expected 100% pass rate, got {summary['scenario_pass_rate_pct']}%"
    assert summary["compliance_accuracy_pct"] == 100.0, f"Expected 100% check compliance, got {summary['compliance_accuracy_pct']}%"
    assert summary["error_rate_pct"] == 0.0, f"Expected 0% error rate, got {summary['error_rate_pct']}%"
    assert summary["dxf_exports_verified"] == summary["total_scenarios"], "Not all scenarios produced valid DXF drawings"
    assert summary["time_savings_vs_manual_pct"] > 99.0, "Expected >99% time savings vs manual calculations"

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
