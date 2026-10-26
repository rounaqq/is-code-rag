"""
Step 9: Hand-calculation cross-checks (written by the author of this repository, not published values).
Compares deterministic engine calculations against hand-calculation cross-checks
written by the author of this repository to verify arithmetic consistency.
Does NOT import, read, print, or quote .env or any secret keys.
"""

import json
import math
from pathlib import Path
import sys
import time
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.validation.is456_flexure import ast_required_singly
from src.validation.is456_shear import shear_design
from src.validation.is456_checks import xu_max_over_d

SP16_FILE = Path("data/eval/sp16_worked_examples.json")
REPORT_FILE = Path("data/eval/sp16_evaluation_report.json")


def evaluate_sp16_benchmarks() -> Dict[str, Any]:
    """
    Evaluates engine calculations against hand-calculation cross-checks
    (written by the author of this repository, not published values).
    """
    if not SP16_FILE.exists():
        raise FileNotFoundError(f"Cross-checks file not found at {SP16_FILE}")

    with open(SP16_FILE, "r", encoding="utf-8") as f:
        examples = json.load(f)

    results: List[Dict[str, Any]] = []
    total = len(examples)
    passed = 0

    print("=" * 105)
    print("STEP 9: HAND-CALCULATION CROSS-CHECKS (WRITTEN BY THE AUTHOR OF THIS REPOSITORY, NOT PUBLISHED VALUES)")
    print(f"Total Cross-Check Examples: {total}")
    print("=" * 105)

    for ex in examples:
        ex_id = ex["example_id"]
        title = ex["title"]
        inp = ex["inputs"]
        ref = ex.get("reference_hand_calc_values")
        tolerance_pct = float(ex.get("tolerance_pct", 3.0))

        if "mu_kNm" in inp:
            # Flexure cross-check example
            b = float(inp["b_mm"])
            d = float(inp["d_mm"])
            fck = float(inp["fck"])
            fy = float(inp["fy"])
            mu_Nmm = float(inp["mu_kNm"]) * 1e6

            mu_bd2_calc = round(mu_Nmm / (b * (d ** 2)), 3)
            flex_res = ast_required_singly(b=b, d=d, fck=fck, fy=fy, mu=mu_Nmm)
            ast_calc = float(flex_res["ast_mm2"])
            pt_calc = round((ast_calc / (b * d)) * 100.0, 3)

            # Compare against reference hand-calculation figures
            pt_ref = float(ref["pt_percent_approx"])
            pt_error_pct = round(abs(pt_calc - pt_ref) / pt_ref * 100.0, 2)
            ast_ref = float(ref["ast_required_mm2_approx"])
            ast_error_pct = round(abs(ast_calc - ast_ref) / ast_ref * 100.0, 2)

            is_under = flex_res["xu_over_d"] <= xu_max_over_d(fy)
            ex_passed = (ast_error_pct <= tolerance_pct) and (is_under == ref["is_under_reinforced"])

            rec = {
                "example_id": ex_id,
                "title": title,
                "type": "Flexure",
                "inputs": inp,
                "calculated": {
                    "mu_over_bd2": mu_bd2_calc,
                    "ast_mm2": round(ast_calc, 2),
                    "pt_percent": pt_calc,
                    "xu_over_d": round(flex_res["xu_over_d"], 3),
                    "is_under_reinforced": is_under,
                },
                "reference_hand_calc": ref,
                "ast_difference_pct": ast_error_pct,
                "ast_variance_pct": ast_error_pct,
                "status": "PASSED" if ex_passed else "FAILED",
            }

            print(f"\n[{ex_id}] {title}")
            print(f"  Inputs: b={b}mm, d={d}mm, M{int(fck)}/Fe{int(fy)}, Mu={inp['mu_kNm']} kNm (Mu/bd^2 = {mu_bd2_calc})")
            print(f"  Reference (hand-calc): Ast ~ {ast_ref} mm2 (pt ~ {pt_ref}%)")
            print(f"  Calculated Engine: Ast = {ast_calc:.2f} mm2 (pt = {pt_calc}%, xu/d = {flex_res['xu_over_d']:.3f})")
            print(f"  Agreement: Ast difference = {ast_error_pct}% (Tolerance: +/-{tolerance_pct}%) -> {'CONGRUENT' if ex_passed else 'DIVERGENT'}")

        else:
            # Shear cross-check example
            b = float(inp["b_mm"])
            d = float(inp["d_mm"])
            fck = float(inp["fck"])
            fy_s = float(inp["fy_stirrup"])
            vu_N = float(inp["vu_kN"]) * 1e3
            ast_prov = float(inp["ast_provided_mm2"])
            stirrup_dia = float(inp["stirrup_dia_mm"])

            shear_res = shear_design(
                b=b,
                d=d,
                fck=fck,
                fy_stirrup=fy_s,
                vu=vu_N,
                ast_provided=ast_prov,
                stirrup_dia=stirrup_dia,
                legs=inp.get("stirrup_legs", 2),
            )

            tau_v_calc = round(shear_res["tau_v"], 3)
            tau_c_calc = round(shear_res["tau_c"], 3)
            spacing_calc = round(float(shear_res["spacing_mm"]), 1)

            sp_ref = float(ref["required_spacing_mm"])
            spacing_error_pct = round(abs(spacing_calc - sp_ref) / sp_ref * 100.0, 2)
            tau_c_match = abs(tau_c_calc - ref["tau_c_N_per_mm2"]) < 0.02
            ex_passed = (spacing_error_pct <= tolerance_pct) and tau_c_match

            rec = {
                "example_id": ex_id,
                "title": title,
                "type": "Shear",
                "inputs": inp,
                "calculated": {
                    "tau_v_N_per_mm2": tau_v_calc,
                    "tau_c_N_per_mm2": tau_c_calc,
                    "shear_status": shear_res["status"],
                    "required_spacing_mm": spacing_calc,
                    "suggested_spacing_mm": shear_res["suggested_spacing_mm"],
                },
                "reference_hand_calc": ref,
                "spacing_difference_pct": spacing_error_pct,
                "spacing_variance_pct": spacing_error_pct,
                "status": "PASSED" if ex_passed else "FAILED",
            }

            print(f"\n[{ex_id}] {title}")
            print(f"  Inputs: b={b}mm, d={d}mm, M{int(fck)}, Vu={inp['vu_kN']} kN, Ast_prov={ast_prov} mm2")
            print(f"  Reference (hand-calc): tau_v={ref['tau_v_N_per_mm2']} N/mm2, tau_c={ref['tau_c_N_per_mm2']} N/mm2, Req Spacing={sp_ref} mm")
            print(f"  Calculated Engine: tau_v={tau_v_calc} N/mm2, tau_c={tau_c_calc} N/mm2, Req Spacing={spacing_calc} mm")
            print(f"  Agreement: Spacing difference = {spacing_error_pct}% (Tolerance: +/-{tolerance_pct}%) -> {'CONGRUENT' if ex_passed else 'DIVERGENT'}")

        if ex_passed:
            passed += 1
        results.append(rec)

    pass_rate = (passed / total) * 100.0 if total > 0 else 0.0

    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pillar_name": "Hand-calculation cross-checks (written by the author of this repository, not published values)",
        "source": "Hand-calculation cross-checks (written by the author of this repository, not published values)",
        "handbook_source": "Hand-calculation cross-checks (written by the author of this repository, not published values)",
        "total_examples": total,
        "examples_passed": passed,
        "pass_rate_pct": round(pass_rate, 2),
        "all_congruent": passed == total,
        "results": results,
    }

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 105)
    print("HAND-CALCULATION CROSS-CHECKS SUMMARY")
    print("=" * 105)
    print(f"Pass Rate:        {pass_rate:.1f}% ({passed}/{total} examples congruent within tolerance)")
    print(f"Report Location:  {REPORT_FILE}")
    print("=" * 105)

    return summary


if __name__ == "__main__":
    evaluate_sp16_benchmarks()
