"""
Step 9 (extension): Independent Engineer Review - blind package + attestation record.

This module builds a BLIND review package for an independent structural engineer:
  * design inputs and the computed designs (the repository author's expected
    answers - `expected_checks` / `governing_clauses` - are deliberately omitted
    so the reviewer is not anchored),
  * the governing assumption list, and
  * the list of items that are not sourced to a code clause ("unsourced items").

It also defines and validates `data/eval/independent_review_record.json`.

HARD RULE - honesty: this module NEVER creates a review record and NEVER invents
a reviewer. It only *reads and validates* a record supplied by a genuine,
independent engineer. A record is rejected when the reviewer equals the author
or when required attestation fields are missing.

Consequently the Step 9 pillar built on this module reads
"PENDING - not evaluated" until a valid record exists, and it is NEVER counted
as a pass. Drawings stay "DRAFT - NOT FOR CONSTRUCTION. Not engineer-reviewed."
until a valid record is loaded; when one is loaded the title block reads
"Reviewed by <name>, <date>: <outcome>" and never "approved".

Does NOT import, read, print, or quote .env or any secret keys.
"""

import json
import re
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.generation.beam_sizing import design_and_validate_beam
from src.cad.engineer_review import STANDARD_ASSUMPTIONS, sign_off_design
from src.cad.beam_dxf import export_dxf_from_design

SCENARIOS_FILE = Path("data/eval/structural_design_scenarios.json")
PACKAGE_FILE = Path("data/eval/independent_review_package.json")
RECORD_FILE = Path("data/eval/independent_review_record.json")
REVIEWED_CAD_DIR = Path("data/processed/cad/independent_review")

PILLAR_PENDING = "PENDING - not evaluated"

ALLOWED_OUTCOMES = [
    "accepted",
    "accepted_with_comments",
    "rejected",
    "needs_revision",
]

REQUIRED_FIELDS = [
    "author_name",
    "reviewer_name",
    "role",
    "registration_number",
    "date",
    "scope",
    "designs",
]

_IS_CLAUSE_RE = re.compile(r"^is\s*456", re.IGNORECASE)
_UNSOURCED_HINT_RE = re.compile(r"empirical|indicative|fig\.?\s*4|constructability", re.IGNORECASE)

PACKAGE_PURPOSE = (
    "Blind review package for an INDEPENDENT structural engineer. It contains the design inputs "
    "and the computed designs only. The repository author's expected answers were deliberately "
    "omitted to keep the review unbiased. Scripts and tests do not create a review record or a "
    "reviewer; the accompanying attestation record must be completed by the reviewer."
)

BLINDNESS_NOTE = (
    "Blind package: `expected_checks` and `governing_clauses` from the scenario source file are "
    "NOT included. The reviewer receives inputs, computed designs, the assumption list and the "
    "unsourced items only."
)


def _load_scenarios() -> List[Dict[str, Any]]:
    if not SCENARIOS_FILE.exists():
        raise FileNotFoundError(f"Scenarios file not found at {SCENARIOS_FILE}")
    with open(SCENARIOS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _scenario_design(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """Runs the deterministic sizing engine for a scenario (no LLM, no network)."""
    inp = scenario["inputs"]
    res = design_and_validate_beam(
        span_m=inp["span_m"],
        dead_load_kN_per_m=inp["dead_load_kN_per_m"],
        live_load_kN_per_m=inp["live_load_kN_per_m"],
        fck=inp["fck"],
        fy=inp["fy"],
        exposure=inp["exposure"],
    )
    return res


def _derive_unsourced_items() -> List[Dict[str, str]]:
    """
    Lists the governing items that are NOT traceable to a specific IS 456 clause
    (engineering judgement, an empirical approximation, or a constructability
    rule). Derived from the shared STANDARD_ASSUMPTIONS list.
    """
    items: List[Dict[str, str]] = []
    for a in STANDARD_ASSUMPTIONS:
        clause = str(a.get("clause", ""))
        value = str(a.get("value", ""))
        if not _IS_CLAUSE_RE.match(clause.strip()) or _UNSOURCED_HINT_RE.search(value):
            items.append({
                "item": a.get("assumption", ""),
                "detail": value,
                "reference": clause,
                "reason": "Engineering judgement / empirical approximation - not a verbatim code clause.",
            })
    return items


def _build_design_entry(scenario: Dict[str, Any], sizing: Dict[str, Any]) -> Dict[str, Any]:
    dims = sizing["section_dimensions"]
    rebar = sizing["reinforcement_detailing"]
    inp = scenario["inputs"]
    return {
        "scenario_id": scenario["scenario_id"],
        "name": scenario["name"],
        "inputs": {
            "span_m": inp["span_m"],
            "dead_load_kN_per_m": inp["dead_load_kN_per_m"],
            "live_load_kN_per_m": inp["live_load_kN_per_m"],
            "fck": inp["fck"],
            "fy": inp["fy"],
            "exposure": inp["exposure"],
        },
        "design": {
            "section": f"{int(dims['b'])}x{int(dims['D'])} mm",
            "b_mm": dims["b"],
            "D_mm": dims["D"],
            "effective_depth_mm": round(dims["d_actual"], 1),
            "cover_mm": int(dims["cover_mm"]),
            "materials": f"M{int(inp['fck'])} / Fe{int(inp['fy'])}",
            "main_reinforcement": f"{rebar['main_bar_count']}-T{int(rebar['main_bar_dia_mm'])}",
            "stirrups": f"2L-T{int(rebar['stirrup_dia_mm'])} @ {int(rebar['stirrup_spacing_mm'])} mm",
            "development_length_mm": round(sizing["development_length"]["ld_mm"], 0),
        },
        "governing_loads": sizing.get("derived_loads", {}),
        "flexure": sizing.get("flexure", {}),
        "shear_summary": {
            "nominal_shear_stress_tau_v": sizing.get("shear", {}).get("nominal_shear_stress_tau_v"),
            "tau_c_max": sizing.get("shear", {}).get("tau_c_max"),
            "shear_status": sizing.get("shear_status"),
        },
        "cited_clauses": sizing.get("is456_citations", []),
    }


def build_blind_package(*, write: bool = True) -> Dict[str, Any]:
    """
    Builds the blind independence-review package (inputs + computed designs, the
    assumption list and the unsourced items). Contains no author expected answers.
    """
    scenarios = _load_scenarios()

    designs: List[Dict[str, Any]] = []
    for sc in scenarios:
        res = _scenario_design(sc)
        sizing = res.get("sizing")
        if not sizing or sizing.get("status") != "ok":
            raise RuntimeError(f"Scenario {sc['scenario_id']} did not produce a valid design.")
        designs.append(_build_design_entry(sc, sizing))

    package = {
        "package_version": "1.0",
        "generated_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "step": 9,
        "title": "Step 9 (extension): Independent Engineer Review - Blind Package",
        "purpose": PACKAGE_PURPOSE,
        "blindness_note": BLINDNESS_NOTE,
        "assumption_list": STANDARD_ASSUMPTIONS,
        "unsourced_items": _derive_unsourced_items(),
        "designs": designs,
        "attestation_record_schema": {
            "file": str(RECORD_FILE),
            "note": (
                "Complete this record as an independent reviewer. It is read and validated only; "
                "this module never creates a record or a reviewer."
            ),
            "required_fields": {
                "author_name": "Name of the person who authored the designs (string).",
                "reviewer_name": "Name of the independent reviewer (string). MUST differ from author_name.",
                "role": "Reviewer's professional role (string).",
                "registration_number": "Reviewer's professional registration / licence number (string).",
                "date": "Review date, ISO 8601 (string).",
                "scope": "Scope of the review (string).",
                "designs": "List of {scenario_id, outcome, comments}; outcome in %s." % ALLOWED_OUTCOMES,
            },
        },
    }

    if write:
        PACKAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PACKAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(package, f, indent=2)

    return package


def load_review_record(path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """
    Reads the attestation record supplied by a reviewer.

    Returns None when no record exists. Raises ValueError when a record exists
    but is not valid JSON. Never creates a record.
    """
    record_path = Path(path) if path is not None else RECORD_FILE
    if not record_path.exists():
        return None
    with open(record_path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Review record at {record_path} is not valid JSON: {exc}") from exc


def _normalize_name(name: Any) -> str:
    return re.sub(r"\s+", " ", str(name or "")).strip().casefold()


def validate_review_record(
    record: Dict[str, Any],
    *,
    expected_scenario_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Validates an attestation record. Pure function - reads no files, writes none.

    Returns {"valid": bool, "reasons": [...]}. A record is invalid when a required
    field is missing/empty, when an outcome is not allowed, when scenario coverage
    is incomplete, or when the reviewer is the author.
    """
    reasons: List[str] = []

    if not isinstance(record, dict):
        return {"valid": False, "reasons": ["Record is not a JSON object."]}

    for field in REQUIRED_FIELDS:
        if field not in record:
            reasons.append(f"Missing required field: '{field}'.")

    def _nonempty_str(field: str) -> bool:
        val = record.get(field)
        return isinstance(val, str) and val.strip() != ""

    for field in ["author_name", "reviewer_name", "role", "registration_number", "date", "scope"]:
        if field in record and not _nonempty_str(field):
            reasons.append(f"Field '{field}' must be a non-empty string.")

    # Reject a record where the reviewer equals the author.
    author = _normalize_name(record.get("author_name"))
    reviewer = _normalize_name(record.get("reviewer_name"))
    if author and reviewer and author == reviewer:
        reasons.append(
            "Reviewer equals the author: an independent review requires a reviewer distinct from the author."
        )

    designs = record.get("designs")
    if designs is not None:
        if not isinstance(designs, list) or not designs:
            reasons.append("Field 'designs' must be a non-empty list of {scenario_id, outcome, comments}.")
        else:
            seen: List[str] = []
            for idx, entry in enumerate(designs):
                if not isinstance(entry, dict):
                    reasons.append(f"designs[{idx}] must be an object.")
                    continue
                sid = entry.get("scenario_id")
                if not isinstance(sid, str) or not sid.strip():
                    reasons.append(f"designs[{idx}] is missing a valid 'scenario_id'.")
                else:
                    seen.append(sid)
                outcome = entry.get("outcome")
                if outcome not in ALLOWED_OUTCOMES:
                    reasons.append(
                        f"designs[{idx}] ('{sid}') has outcome '{outcome}'; allowed: {ALLOWED_OUTCOMES}."
                    )
                if not isinstance(entry.get("comments", ""), str):
                    reasons.append(f"designs[{idx}] ('{sid}') 'comments' must be a string.")

            if expected_scenario_ids:
                missing = [s for s in expected_scenario_ids if s not in seen]
                if missing:
                    reasons.append(f"No review outcome recorded for: {', '.join(missing)}.")

    return {"valid": len(reasons) == 0, "reasons": reasons}


def evaluate_independent_review() -> Dict[str, Any]:
    """
    The Step 9 independent-review pillar.

    Always returns `counts_toward_pass: False`. The status is
    "PENDING - not evaluated" unless a valid, independent attestation record is
    present. When a valid record is present the reviewer attestation is echoed,
    but the pillar is still never counted as a pass.
    """
    scenarios = _load_scenarios()
    expected_ids = [sc["scenario_id"] for sc in scenarios]

    result: Dict[str, Any] = {
        "pillar": "independent_engineer_review",
        "status": PILLAR_PENDING,
        "counts_toward_pass": False,
        "record_present": False,
        "package_path": str(PACKAGE_FILE),
        "record_path": str(RECORD_FILE),
    }

    try:
        record = load_review_record()
    except ValueError as exc:
        result["record_present"] = True
        result["reasons"] = [str(exc)]
        result["reason"] = "A review record file exists but could not be parsed."
        return result

    if record is None:
        result["reason"] = (
            "No independent review record present. Scripts and tests never create a record or a "
            "reviewer, so this pillar remains PENDING until a genuine reviewer supplies one."
        )
        return result

    result["record_present"] = True
    validation = validate_review_record(record, expected_scenario_ids=expected_ids)
    if not validation["valid"]:
        result["reasons"] = validation["reasons"]
        result["reason"] = "The supplied record was rejected; the pillar remains PENDING."
        return result

    per_design = [
        {
            "scenario_id": d.get("scenario_id"),
            "outcome": d.get("outcome"),
            "comments": d.get("comments", ""),
        }
        for d in record.get("designs", [])
    ]

    result.update({
        "status": "REVIEWED - not approved",
        "reviewer": {
            "name": record.get("reviewer_name"),
            "role": record.get("role"),
            "registration_number": record.get("registration_number"),
            "date": record.get("date"),
            "scope": record.get("scope"),
        },
        "author_name": record.get("author_name"),
        "per_design": per_design,
        "reason": (
            "A valid independent review record is present. It is recorded but never counted as a "
            "pass; drawings read 'Reviewed by <name>, <date>: <outcome>' and never 'approved'."
        ),
    })
    return result


def stamp_drawings_from_record(
    record: Dict[str, Any],
    *,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Stamps drawings with the reviewer attestation 'Reviewed by <name>, <date>:
    <outcome>' from a VALID record. Refuses to run on an invalid record, so
    drawings cannot be stamped without a genuine, independent reviewer.
    Never writes 'approved'.
    """
    validation = validate_review_record(
        record,
        expected_scenario_ids=[sc["scenario_id"] for sc in _load_scenarios()],
    )
    if not validation["valid"]:
        raise ValueError("Refusing to stamp drawings: review record is invalid: " + "; ".join(validation["reasons"]))

    out_dir = Path(output_dir) if output_dir is not None else REVIEWED_CAD_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    outcomes = {
        d.get("scenario_id"): (d.get("outcome"), d.get("comments", ""))
        for d in record.get("designs", [])
    }

    stamped: List[Dict[str, Any]] = []
    for sc in _load_scenarios():
        sid = sc["scenario_id"]
        outcome, comments = outcomes.get(sid, ("Reviewed", ""))
        res = _scenario_design(sc)
        sizing = res["sizing"]
        design_dict = dict(sizing["design_dict"])
        design_dict["span_m"] = sc["inputs"]["span_m"]

        signed = sign_off_design(
            design=design_dict,
            reviewer_name=record["reviewer_name"],
            reviewer_role=record["role"],
            review_date=record["date"],
            outcome=outcome,
            remarks=comments,
        )
        dxf_path = out_dir / f"reviewed_{sid}.dxf"
        export_dxf_from_design(design=signed, output_path=str(dxf_path), validate_first=True)
        stamped.append({
            "scenario_id": sid,
            "outcome": outcome,
            "dxf_path": str(dxf_path),
            "title_block_status": f"Reviewed by {record['reviewer_name']}, {record['date']}: {outcome}",
        })

    return {
        "reviewed_by": record["reviewer_name"],
        "review_date": record["date"],
        "count": len(stamped),
        "drawings": stamped,
    }


def main() -> None:
    package = build_blind_package()
    pillar = evaluate_independent_review()

    print("=" * 100)
    print("STEP 9 (EXTENSION): INDEPENDENT ENGINEER REVIEW")
    print("=" * 100)
    print(f"Blind package:   {PACKAGE_FILE} ({len(package['designs'])} designs)")
    print(f"Unsourced items: {len(package['unsourced_items'])}")
    print(f"Review record:   {RECORD_FILE}")
    print(f"Pillar status:   {pillar['status']}")
    print(f"Counts as pass:  {pillar['counts_toward_pass']}")
    print(f"Note:            {pillar.get('reason', '')}")
    print("=" * 100)


if __name__ == "__main__":
    main()
