"""
Unit tests for Step 9: Structural Design Evaluation & Benchmark.
Validates CAD DXF generation, self-consistency checks, arithmetic re-checks,
and structural engineering disclaimer across design scenarios.
Does NOT read .env or call external networks.
"""

from pathlib import Path
import pytest
from src.evaluation.run_design_eval import run_full_design_evaluation, REPORT_OUTPUT_FILE


def test_step9_full_design_evaluation_benchmark():
    """Step 9 benchmark evaluation across real-world design scenarios."""
    summary = run_full_design_evaluation()

    assert summary["total_scenarios"] >= 5
    assert summary["scenarios_passed"] > 0
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
