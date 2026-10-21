"""
Unit tests for IS 456 limiting depth of neutral axis table (data/processed/is456_xu_max_table.json)
and function xu_max_over_d in src/validation/is456_checks.py.
"""

import json
from pathlib import Path
import pytest

from src.validation.is456_checks import xu_max_over_d

TABLE_PATH = Path("data/processed/is456_xu_max_table.json")


def test_xu_max_table_structure_and_values():
    assert TABLE_PATH.exists(), f"File not found: {TABLE_PATH}"

    # Open files with encoding="utf-8" as required
    with open(TABLE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Exactly 3 rows
    rows = data.get("rows", [])
    assert len(rows) == 3, f"Expected exactly 3 rows, got {len(rows)}"

    expected_fy = [250, 415, 500]
    actual_fy = [r["fy_N_per_mm2"] for r in rows]
    assert actual_fy == expected_fy, f"Expected fy values {expected_fy}, got {actual_fy}"

    # 2. Values strictly decrease as fy increases
    xu_values = [r["xu_max_over_d"] for r in rows]
    for i in range(len(xu_values) - 1):
        assert xu_values[i] > xu_values[i + 1], (
            f"xu_max_over_d values not strictly decreasing: {xu_values[i]} not > {xu_values[i + 1]}"
        )

    # 3. Verified is true
    assert data.get("verified") is True, "Table is not marked as verified"
    assert data.get("verified_by") == "Rounaq, manual check against page_083.png"
    assert data.get("code_id") == "IS 456"
    assert data.get("edition_year") == 2000
    assert data.get("clause_reference") == "38.1"


def test_xu_max_over_d_function():
    """Checks exact values for 250, 415, 500 and rejection without interpolation for any other fy."""
    assert xu_max_over_d(250) == 0.53
    assert xu_max_over_d(415) == 0.48
    assert xu_max_over_d(500) == 0.46

    # Test float equivalents
    assert xu_max_over_d(250.0) == 0.53
    assert xu_max_over_d(415.0) == 0.48
    assert xu_max_over_d(500.0) == 0.46

    # Any other fy raises ValueError("needs engineer decision")
    for bad_fy in [240, 300, 350, 450, 550, 600, -250, 0]:
        with pytest.raises(ValueError) as exc_info:
            xu_max_over_d(bad_fy)
        assert "needs engineer decision" in str(exc_info.value)

    # Invalid types or None
    for invalid in [None, "invalid", True, False]:
        with pytest.raises(ValueError) as exc_info:
            xu_max_over_d(invalid)
        assert "needs engineer decision" in str(exc_info.value)
