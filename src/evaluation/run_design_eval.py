"""
Step 9: End-to-End IS 456 Structural Design Evaluation & Validation Framework.
Evaluates:
  1. Self-consistency checks (the same code designs and checks).
  2. Arithmetic re-check from the JSON tables (uses the same Vu and the same Table 19 row rule as the sizing).
  3. Physical safety boundaries (under-reinforced sections, shear ceilings).
  4. 2D CAD DXF export validity.
  5. Execution latency metrics.
Does NOT import, read, print, or quote .env or any secret keys.
"""

import json
import math
from pathlib import Path
import sys
import time
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import ezdxf

from src.generation.beam_sizing import design_and_validate_beam
from src.cad.beam_dxf import export_dxf_from_design

SCENARIOS_FILE = Path("data/eval/structural_design_scenarios.json")
REPORT_OUTPUT_FILE = Path("data/eval/design_evaluation_report.json")


def independent_shear_check(
    b: float,
    d: float,
    fck: float,
    fy: float,
    vu_kN: float,
    ast_provided: float,
    stirrup_dia: float,
    drawn_spacing_mm: float,
) -> Dict[str, Any]:
    """
    Arithmetic re-check from the JSON tables (uses the same Vu and the same Table 19
    row rule as the sizing).
    Recomputes tau_v, tau_c, and required spacing directly from is456_table_19.json
    and is456_table_20.json without calling sizing code.
    Reports any scenario where drawn spacing > required spacing.
    """
    t19_path = Path("data/processed/is456_table_19.json")
    t20_path = Path("data/processed/is456_table_20.json")

    with open(t19_path, "r", encoding="utf-8") as f:
        t19_data = json.load(f)
    with open(t20_path, "r", encoding="utf-8") as f:
        t20_data = json.load(f)

    # 1. tau_v = Vu / (b * d) (IS 456 Cl. 40.1)
    vu_N = vu_kN * 1000.0
    tau_v = vu_N / (b * d)

    # 2. tau_c_max from Table 20 JSON directly
    grade_key = f"M{int(round(fck))}" if fck < 40 else "M40 and above"
    tau_c_max_val = None
    for r in t20_data["rows"]:
        if r["grade"] == grade_key:
            tau_c_max_val = float(r["tau_c_max"])
            break
    if tau_c_max_val is None:
        raise ValueError(f"Could not find grade {grade_key} in Table 20 rows.")

    # 3. tau_c lookup from Table 19 JSON directly
    # Row rule: row at or below pt (first row if pt < 0.15, last row if pt >= 3.0)
    pt = (100.0 * ast_provided) / (b * d)
    if fck in (15.0, 15):
        col = "M15"
    elif fck in (20.0, 20):
        col = "M20"
    elif fck in (25.0, 25):
        col = "M25"
    elif fck in (30.0, 30):
        col = "M30"
    elif fck in (35.0, 35):
        col = "M35"
    elif fck >= 40.0:
        col = "M40 and above"
    else:
        raise ValueError(f"Unknown concrete grade for fck={fck}")

    rows = t19_data["rows"]
    if pt < 0.15:
        chosen_row = rows[0]
    elif pt >= 3.0:
        chosen_row = rows[-1]
    else:
        eligible = [r for r in rows if r["pt_value"] <= pt]
        chosen_row = eligible[-1]
    tau_c = float(chosen_row["tau_c"][col])

    # 4. Two-legged stirrup area & spacing limits
    asv = 2.0 * math.pi * (stirrup_dia ** 2) / 4.0
    fy_eff = min(float(fy), 415.0)

    sv_min_steel = (0.87 * fy_eff * asv) / (0.4 * b)
    sv_cap = min(0.75 * d, 300.0)

    # 5. Required spacing
    if tau_v <= tau_c:
        vus = 0.0
        sv_calc = None
        required_spacing = min(sv_min_steel, sv_cap)
    else:
        vus = vu_N - (tau_c * b * d)
        sv_calc = (0.87 * fy_eff * asv * d) / vus
        required_spacing = min(sv_calc, sv_min_steel, sv_cap)

    # Check if drawn spacing > required spacing (with float tolerance 1e-4)
    drawn_exceeds_required = drawn_spacing_mm > (required_spacing + 1e-4)
    shear_check_passed = (not drawn_exceeds_required) and (tau_v <= tau_c_max_val)

    return {
        "tau_v": round(tau_v, 3),
        "tau_c": round(tau_c, 3),
        "tau_c_max": round(tau_c_max_val, 3),
        "pt": round(pt, 3),
        "vus_kN": round(vus / 1000.0, 3) if vus > 0 else 0.0,
        "required_spacing_mm": round(required_spacing, 2),
        "drawn_spacing_mm": round(drawn_spacing_mm, 2),
        "drawn_exceeds_required": drawn_exceeds_required,
        "shear_check_passed": shear_check_passed,
    }


def run_full_design_evaluation() -> Dict[str, Any]:
    """
    Executes the Step 9 evaluation benchmark across all real-world design scenarios.
    Returns comprehensive evaluation metrics.
    """
    if not SCENARIOS_FILE.exists():
        raise FileNotFoundError(f"Scenarios file not found at {SCENARIOS_FILE}")

    with open(SCENARIOS_FILE, "r", encoding="utf-8") as f:
        scenarios = json.load(f)

    total_scenarios = len(scenarios)
    passed_scenarios = 0
    total_checks_evaluated = 0
    total_checks_passed = 0
    dxf_exports_verified = 0

    scenario_reports = []
    total_latency_ms = 0.0

    print("=" * 100)
    print("STEP 9: IS 456:2000 STRUCTURAL DESIGN EVALUATION & VALIDATION")
    print(f"Total Benchmark Scenarios: {total_scenarios}")
    print("=" * 100)

    for sc in scenarios:
        sc_id = sc["scenario_id"]
        sc_name = sc["name"]
        inputs = sc["inputs"]
        expected = sc["expected_checks"]

        t_start = time.perf_counter()

        # 1. Run automated beam design and validation
        res = design_and_validate_beam(
            span_m=inputs["span_m"],
            dead_load_kN_per_m=inputs["dead_load_kN_per_m"],
            live_load_kN_per_m=inputs["live_load_kN_per_m"],
            fck=inputs["fck"],
            fy=inputs["fy"],
            exposure=inputs["exposure"],
        )

        latency = (time.perf_counter() - t_start) * 1000.0
        total_latency_ms += latency

        sizing = res["sizing"]
        validation = res["validation"]

        # Check compliance
        checks = validation["checks"]
        for c in checks:
            total_checks_evaluated += 1
            if c["passed"]:
                total_checks_passed += 1

        # 2. Verify 2D CAD DXF Generation
        dxf_path = Path("data/processed/cad") / f"eval_{sc_id}.dxf"
        dxf_res = export_dxf_from_design(sizing["design_dict"], str(dxf_path), validate_first=True)
        dxf_valid = False
        if dxf_res["status"] == "success" and dxf_path.exists():
            try:
                doc = ezdxf.readfile(str(dxf_path))
                dxf_valid = len(list(doc.modelspace())) > 20
                if dxf_valid:
                    dxf_exports_verified += 1
            except Exception:
                dxf_valid = False

        # 3. Verify Code-Grounding & Engineering Limits
        dims = sizing["section_dimensions"]
        flex = sizing["flexure"]
        shear = sizing["shear"]
        rebar = sizing["reinforcement_detailing"]

        under_reinforced = flex["xu_over_d"] <= 0.48
        shear_safe = shear["shear_safe"]
        shear_status = sizing.get("shear_status", "minimum_shear_steel_ok")
        cover_correct = dims["cover_mm"] == expected["cover_mm"]

        # 4. Independent Shear Check (recomputed directly from JSON files, not calling sizing code)
        indep_shear = independent_shear_check(
            b=dims["b"],
            d=dims["d"],
            fck=inputs["fck"],
            fy=inputs["fy"],
            vu_kN=sizing["derived_loads"]["factored_shear_Vu_kN"],
            ast_provided=rebar["main_bar_area_provided_mm2"],
            stirrup_dia=rebar["stirrup_dia_mm"],
            drawn_spacing_mm=rebar["stirrup_spacing_mm"],
        )

        scenario_passed = (
            validation["status"] == "passed"
            and all(c["passed"] for c in checks)
            and indep_shear["shear_check_passed"]
        )
        if scenario_passed:
            passed_scenarios += 1

        record = {
            "scenario_id": sc_id,
            "name": sc_name,
            "span_m": inputs["span_m"],
            "section": f"{int(dims['b'])}x{int(dims['D'])} mm",
            "d_mm": int(dims['d']),
            "cover_mm": int(dims['cover_mm']),
            "cover_correct": cover_correct,
            "Mu_kNm": sizing["derived_loads"]["factored_moment_Mu_kNm"],
            "Vu_kN": sizing["derived_loads"]["factored_shear_Vu_kN"],
            "rebar": f"{rebar['main_bar_count']}-T{int(rebar['main_bar_dia_mm'])}",
            "stirrups": f"2L-T{int(rebar['stirrup_dia_mm'])} @ {int(rebar['stirrup_spacing_mm'])} c/c",
            "under_reinforced": under_reinforced,
            "shear_safe": shear_safe,
            "shear_status": shear_status,
            "status": "PASSED" if scenario_passed else "FAILED",
            "checks_passed": f"{sum(1 for c in checks if c['passed'])}/{len(checks)}",
            "self_consistency_checks": f"{sum(1 for c in checks if c['passed'])}/{len(checks)}",
            "dxf_generated": dxf_valid,
            "latency_ms": round(latency, 2),
            "independent_shear": indep_shear,
            "arithmetic_recheck_from_json_tables": indep_shear,
        }
        scenario_reports.append(record)

        print(f"\n[{sc_id}] {sc_name}")
        print(f"  Inputs: Span={inputs['span_m']}m, DL={inputs['dead_load_kN_per_m']}kN/m, LL={inputs['live_load_kN_per_m']}kN/m, M{int(inputs['fck'])}/Fe{int(inputs['fy'])}, {inputs['exposure']}")
        print(f"  Sized Section: {int(dims['b'])} x {int(dims['D'])} mm (d={int(dims['d'])} mm, Cover={int(dims['cover_mm'])} mm)")
        print(f"  Forces: Mu = {sizing['derived_loads']['factored_moment_Mu_kNm']} kNm, Vu = {sizing['derived_loads']['factored_shear_Vu_kN']} kN")
        print(f"  Detailing: Bottom={record['rebar']}, Stirrups={record['stirrups']}")
        print(f"  Arithmetic re-check from the JSON tables (uses the same Vu and the same Table 19 row rule as the sizing): tau_v={indep_shear['tau_v']} N/mm2, tau_c={indep_shear['tau_c']} N/mm2, Vus={indep_shear['vus_kN']} kN | Req Spacing={indep_shear['required_spacing_mm']} mm, Drawn={indep_shear['drawn_spacing_mm']} mm -> {'SAFE' if not indep_shear['drawn_exceeds_required'] else 'VIOLATION'}")
        if indep_shear["drawn_exceeds_required"]:
            print(f"  [ERROR] Drawn spacing ({indep_shear['drawn_spacing_mm']} mm) EXCEEDS required spacing ({indep_shear['required_spacing_mm']} mm)!")
        print(f"  Self-consistency checks (the same code designs and checks): {record['checks_passed']} passed | Under-reinforced: {under_reinforced} | Shear safe: {shear_safe} | Shear status: {shear_status}")
        print(f"  CAD DXF Export: {'VALID' if dxf_valid else 'ERROR'} ({dxf_path.name}) | Time: {record['latency_ms']} ms")

    # Metrics Summary
    scenario_pass_rate = (passed_scenarios / total_scenarios) * 100.0
    avg_latency_ms = total_latency_ms / total_scenarios if total_scenarios > 0 else 0.0

    stirrups_designed_count = sum(1 for r in scenario_reports if r.get("shear_status") == "stirrups_designed")
    min_shear_steel_count = sum(1 for r in scenario_reports if r.get("shear_status") in ("minimum_shear_steel", "minimum_shear_steel_ok"))
    shear_violations = [
        r["scenario_id"] for r in scenario_reports
        if r["independent_shear"]["drawn_exceeds_required"]
    ]

    summary = {
        "evaluation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_scenarios": total_scenarios,
        "scenarios_passed": passed_scenarios,
        "scenario_pass_rate_pct": round(scenario_pass_rate, 2),
        "total_checks_evaluated": total_checks_evaluated,
        "total_checks_passed": total_checks_passed,
        "self_consistency_checks_passed": f"{total_checks_passed}/{total_checks_evaluated}",
        "dxf_exports_verified": dxf_exports_verified,
        "avg_latency_ms": round(avg_latency_ms, 2),
        "stirrups_designed_count": stirrups_designed_count,
        "minimum_shear_steel_count": min_shear_steel_count,
        "shear_spacing_violations": shear_violations,
        "arithmetic_recheck_from_json_tables_all_passed": len(shear_violations) == 0,
        "scenario_reports": scenario_reports,
        "disclaimer": "These results are not an independent validation. A structural engineer must review the designs.",
    }

    print("\n" + "=" * 100)
    print("STEP 9 EVALUATION BENCHMARK SUMMARY")
    print("=" * 100)
    print(f"Scenario Pass Rate:          {summary['scenario_pass_rate_pct']}% ({passed_scenarios}/{total_scenarios})")
    print(f"Self-consistency checks (the same code designs and checks): {total_checks_passed}/{total_checks_evaluated} passed")
    print(f"CAD DXF Export Success:      {dxf_exports_verified}/{total_scenarios} drawings generated & verified")
    print(f"Shear Status Breakdown:      {stirrups_designed_count}/{total_scenarios} stirrups_designed, {min_shear_steel_count}/{total_scenarios} minimum_shear_steel")
    print(f"Arithmetic re-check from the JSON tables (uses the same Vu and the same Table 19 row rule as the sizing): {'ALL PASSED' if len(shear_violations) == 0 else f'VIOLATIONS in {shear_violations}'} (Drawn spacing <= Required spacing)")
    print(f"Average Automated Latency:   {summary['avg_latency_ms']} ms per beam")
    print("=" * 100)
    print("These results are not an independent validation. A structural engineer must review the designs.")
    print("=" * 100)

    REPORT_OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary


if __name__ == "__main__":
    run_full_design_evaluation()
