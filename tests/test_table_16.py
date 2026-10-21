"""
Unit tests for IS 456 Table 16 data.
"""

import json
from pathlib import Path

TABLE_16_PATH = Path("data/processed/is456_table_16.json")


def test_table_16_structure_and_values():
    assert TABLE_16_PATH.exists(), f"File not found: {TABLE_16_PATH}"
    with open(TABLE_16_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Exactly 5 rows with the expected exposure names
    expected_exposures = ["Mild", "Moderate", "Severe", "Very severe", "Extreme"]
    rows = data.get("rows", [])
    assert len(rows) == 5, f"Expected 5 rows, got {len(rows)}"
    actual_exposures = [r["exposure"] for r in rows]
    assert actual_exposures == expected_exposures, (
        f"Exposure names mismatch: expected {expected_exposures}, got {actual_exposures}"
    )

    # 2. Cover values strictly increase from Mild to Extreme
    covers = [r["nominal_cover_mm"] for r in rows]
    for i in range(len(covers) - 1):
        assert covers[i] < covers[i + 1], (
            f"Cover values not strictly increasing: {covers[i]} not < {covers[i + 1]}"
        )

    # 3. Exactly 3 notes
    notes = data.get("notes", [])
    assert len(notes) == 3, f"Expected 3 notes, got {len(notes)}"

    # 4. Verified is true
    assert data.get("verified") is True, "Table 16 is not marked as verified"
