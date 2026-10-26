"""
Step 8: Structural Engineer Review Workflow & Draft CAD Generation.
Generates structured review sheets listing all parameters, checks, and assumptions.
Evaluates IS 456:2000 clause compliance for each design.
Exports draft 2D CAD DXF drawings with:
  "STATUS: DRAFT - NOT FOR CONSTRUCTION. Not engineer-reviewed."
Scripts and tests do not auto-approve or invent a reviewer.
Does NOT import, read, print, or quote .env or any secret keys.
"""

import json
from pathlib import Path
import sys
import time
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.generation.beam_sizing import size_beam_from_loads
from src.cad.beam_dxf import export_dxf_from_design
from src.cad.engineer_review import generate_review_report

SCENARIOS_FILE = Path("data/eval/structural_design_scenarios.json")
PACKAGE_OUTPUT_FILE = Path("data/eval/engineer_review_package.json")
CAD_DIR = Path("data/processed/cad")


def run_all_engineer_reviews() -> Dict[str, Any]:
    """
    Executes Step 8 engineer review report generation and draft CAD drawing export
    for all 5 benchmark scenarios without auto-approving or inventing a reviewer.
    """
    if not SCENARIOS_FILE.exists():
        raise FileNotFoundError(f"Scenarios file not found at {SCENARIOS_FILE}")

    CAD_DIR.mkdir(parents=True, exist_ok=True)
    PACKAGE_OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(SCENARIOS_FILE, "r", encoding="utf-8") as f:
        scenarios = json.load(f)

    total = len(scenarios)
    reviewed_count = 0
    package_results = []

    print("=" * 105)
    print("STEP 8: IS 456:2000 STRUCTURAL DESIGN REVIEW WORKFLOW (DRAFT DRAWINGS)")
    print(f"Total Benchmark Designs: {total}")
    print("Status: DRAFT - NOT FOR CONSTRUCTION. Not engineer-reviewed.")
    print("=" * 105)

    for sc in scenarios:
        sc_id = sc["scenario_id"]
        sc_name = sc["name"]
        inp = sc["inputs"]

        # 1. Automated preliminary beam sizing
        sizing = size_beam_from_loads(
            span_m=inp["span_m"],
            dead_load_kN_per_m=inp["dead_load_kN_per_m"],
            live_load_kN_per_m=inp["live_load_kN_per_m"],
            fck=inp["fck"],
            fy=inp["fy"],
            exposure=inp["exposure"],
        )

        if sizing["status"] != "ok":
            print(f"[{sc_id}] SKIPPED: Sizing returned status '{sizing['status']}': {sizing.get('reason')}")
            continue

        # 2. Generate formal Engineer Review Sheet
        review_report = generate_review_report(sizing)
        reviewed_count += 1

        # 3. Export draft 2D CAD DXF drawing (no auto-approval, no invented reviewer)
        design_dict = dict(sizing["design_dict"])
        design_dict["span_m"] = inp["span_m"]
        dxf_path = CAD_DIR / f"draft_{sc_id}.dxf"
        dxf_res = export_dxf_from_design(
            design=design_dict,
            output_path=str(dxf_path),
            validate_first=True,
        )

        dims = sizing["section_dimensions"]
        rebar = sizing["reinforcement_detailing"]
        summary = review_report["design_summary"]

        package_results.append({
            "scenario_id": sc_id,
            "name": sc_name,
            "span_m": inp["span_m"],
            "section": f"{int(dims['b'])}x{int(dims['D'])} mm",
            "d_actual_mm": round(dims["d_actual"], 1),
            "cover_mm": int(dims["cover_mm"]),
            "materials": f"M{int(inp['fck'])} / Fe{int(inp['fy'])}",
            "exposure": inp["exposure"],
            "rebar": f"{rebar['main_bar_count']}-T{int(rebar['main_bar_dia_mm'])}",
            "clear_gap_mm": summary["clear_gap_mm"],
            "stirrups": f"2L-T{int(rebar['stirrup_dia_mm'])} @ {int(rebar['stirrup_spacing_mm'])} mm",
            "review_status": review_report["review_status"],
            "dxf_status": "DRAFT - NOT FOR CONSTRUCTION. Not engineer-reviewed.",
            "dxf_path": str(dxf_path),
            "checks": review_report["checks"],
            "markdown_report": review_report["markdown_report"],
        })

        print(f"\n[{sc_id}] {sc_name}")
        print(f"  Section: {int(dims['b'])}x{int(dims['D'])} mm (d={dims['d_actual']:.1f} mm, Cover={int(dims['cover_mm'])} mm, {inp['exposure']})")
        print(f"  Rebar: Bottom={summary['main_bars']} (Gap={summary['clear_gap_mm']} mm) | Stirrups={summary['stirrups']}")
        print(f"  Checks: {sum(1 for c in review_report['checks'] if c['status'] == 'pass')}/{len(review_report['checks'])} IS 456 clauses passed")
        print(f"  CAD DXF: Draft drawing exported to {dxf_path.name}")

    summary_data = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_scenarios": total,
        "reviewed_scenarios": reviewed_count,
        "drawing_status": "DRAFT - NOT FOR CONSTRUCTION. Not engineer-reviewed.",
        "package_results": package_results,
    }

    with open(PACKAGE_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    print("\n" + "=" * 105)
    print("STEP 8 ENGINEER REVIEW PACKAGE SUMMARY")
    print("=" * 105)
    print(f"Total Reviewed:   {reviewed_count}/{total} designs")
    print(f"Drawing Status:   DRAFT - NOT FOR CONSTRUCTION. Not engineer-reviewed.")
    print(f"Review Package:   {PACKAGE_OUTPUT_FILE}")
    print(f"CAD DXF Outputs:  data/processed/cad/draft_SCEN-*.dxf")
    print("=" * 105)

    return summary_data


if __name__ == "__main__":
    run_all_engineer_reviews()
