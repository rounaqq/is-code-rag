"""
Unit tests for IS 456 Table 20 (data/processed/is456_table_20.json)
and function tau_c_max in src/validation/is456_checks.py.
"""

import json
from pathlib import Path
import pytest

from src.validation.is456_checks import tau_c_max

TABLE_20_PATH = Path("data/processed/is456_table_20.json")


def test_table_20_structure_and_values():
    assert TABLE_20_PATH.exists(), f"File not found: {TABLE_20_PATH}"

    # Open files with encoding="utf-8" as required
    with open(TABLE_20_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Exactly 6 rows
    rows = data.get("rows", [])
    assert len(rows) == 6, f"Expected exactly 6 rows, got {len(rows)}"

    expected_grades = ["M15", "M20", "M25", "M30", "M35", "M40 and above"]
    actual_grades = [r["grade"] for r in rows]
    assert actual_grades == expected_grades, f"Expected grades {expected_grades}, got {actual_grades}"

    expected_tau = [2.5, 2.8, 3.1, 3.5, 3.7, 4.0]
    actual_tau = [r["tau_c_max"] for r in rows]
    assert actual_tau == expected_tau, f"Expected tau_c_max values {expected_tau}, got {actual_tau}"

    # 2. Values strictly increase with grade
    for i in range(len(actual_tau) - 1):
        assert actual_tau[i] < actual_tau[i + 1], (
            f"tau_c_max values not strictly increasing: {actual_tau[i]} not < {actual_tau[i + 1]}"
        )

    # 3. Verified is true and metadata matches
    assert data.get("verified") is True, "Table is not marked as verified"
    assert data.get("verified_by") == "Rounaq, manual check against page_086.png"
    assert data.get("code_id") == "IS 456"
    assert data.get("edition_year") == 2000
    assert data.get("table_number") == 20
    assert data.get("title") == "Maximum Shear Stress"
    assert data.get("symbol") == "tau_c_max"
    assert data.get("units") == "N/mm2"
    assert data.get("clause_references") == ["40.2.3", "40.2.3.1", "40.5.1", "41.3.1"]
    assert data.get("page_number") == 86


def test_tau_c_max_function():
    """Checks exact values for M15..M35, M40 and above, and rejection for grades below M15."""
    assert tau_c_max("M15") == 2.5
    assert tau_c_max("M20") == 2.8
    assert tau_c_max("M25") == 3.1
    assert tau_c_max("M30") == 3.5
    assert tau_c_max("M35") == 3.7
    assert tau_c_max("M40 and above") == 4.0

    # Numeric and case-insensitive equivalents
    assert tau_c_max("m15") == 2.5
    assert tau_c_max("m20") == 2.8
    assert tau_c_max("m25") == 3.1
    assert tau_c_max("m30") == 3.5
    assert tau_c_max("m35") == 3.7
    assert tau_c_max(15) == 2.5
    assert tau_c_max(20) == 2.8
    assert tau_c_max(25) == 3.1
    assert tau_c_max(30) == 3.5
    assert tau_c_max(35) == 3.7

    # Any other grade at or above M40 returns the "M40 and above" value (4.0)
    for g in ["M40", "M45", "M50", "M55", "M60", "M80", 40, 45, 50, 60, 80]:
        assert tau_c_max(g) == 4.0

    # Grades below M15 raise ValueError("needs engineer decision")
    for low_grade in ["M10", "M5", "M0", 10, 5, 0, -15]:
        with pytest.raises(ValueError) as exc_info:
            tau_c_max(low_grade)
        assert "needs engineer decision" in str(exc_info.value)

    # Unknown, non-standard, or invalid types raise ValueError("needs engineer decision")
    for bad_input in ["M18", "M22", "unknown", None, True, False]:
        with pytest.raises(ValueError) as exc_info:
            tau_c_max(bad_input)
        assert "needs engineer decision" in str(exc_info.value)
