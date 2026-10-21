"""
Unit tests for IS 456 Table 19 data.
"""

import json
from pathlib import Path

TABLE_19_PATH = Path("data/processed/is456_table_19.json")


def test_table_19_structure():
    assert TABLE_19_PATH.exists(), f"File not found: {TABLE_19_PATH}"
    with open(TABLE_19_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Exactly 13 rows
    rows = data.get("rows", [])
    assert len(rows) == 13, f"Expected 13 rows, got {len(rows)}"

    # 2. Exactly 6 grades in every row matching column_headings
    expected_headings = ["M15", "M20", "M25", "M30", "M35", "M40 and above"]
    assert data.get("column_headings") == expected_headings, (
        f"Column headings mismatch: {data.get('column_headings')}"
    )

    for idx, row in enumerate(rows):
        tau_c = row.get("tau_c", {})
        assert len(tau_c) == 6, (
            f"Row {idx} ({row.get('pt_label')}) has {len(tau_c)} grades, expected 6"
        )
        assert list(tau_c.keys()) == expected_headings, (
            f"Row {idx} ({row.get('pt_label')}) grades mismatch: {list(tau_c.keys())}"
        )

    # 3. Verified is true
    assert data.get("verified") is True, "Table 19 is not marked as verified"


def test_table_19_monotonic_across_rows():
    """Values never decrease from M15 to M40 and above within any row."""
    with open(TABLE_19_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    expected_headings = data.get("column_headings", [])
    rows = data.get("rows", [])

    for r_idx, row in enumerate(rows):
        pt_label = row.get("pt_label")
        tau_c = row.get("tau_c", {})
        for c_idx in range(len(expected_headings) - 1):
            g_curr = expected_headings[c_idx]
            g_next = expected_headings[c_idx + 1]
            val_curr = tau_c[g_curr]
            val_next = tau_c[g_next]
            assert val_curr <= val_next, (
                f"Row {r_idx} (pt={pt_label}): value decreased across grades from "
                f"{g_curr}={val_curr} to {g_next}={val_next}"
            )


def test_table_19_monotonic_down_columns():
    """Values never decrease going down the rows within any column."""
    with open(TABLE_19_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    expected_headings = data.get("column_headings", [])
    rows = data.get("rows", [])

    for g in expected_headings:
        for r_idx in range(len(rows) - 1):
            row_curr = rows[r_idx]
            row_next = rows[r_idx + 1]
            val_curr = row_curr["tau_c"][g]
            val_next = row_next["tau_c"][g]
            assert val_curr <= val_next, (
                f"Column {g}: value decreased down rows from "
                f"row {r_idx} (pt={row_curr['pt_label']}, val={val_curr}) to "
                f"row {r_idx + 1} (pt={row_next['pt_label']}, val={val_next})"
            )
