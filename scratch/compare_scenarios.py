import json
from src.generation.beam_sizing import size_beam_from_loads

scenarios = json.load(open("data/eval/structural_design_scenarios.json"))

old_data = {
    "SCEN-01": {
        "bars": "6-T12",
        "clear_gap": 20.40,
        "ast": 678.58,
        "d_actual": 341.0,
        "stirrup_spacing": 250.0,
        "ld": 565,
        "actual_ld": 11.73,
    },
    "SCEN-02": {
        "bars": "4-T20",
        "clear_gap": 48.00,
        "ast": 1256.64,
        "d_actual": 477.0,
        "stirrup_spacing": 300.0,
        "ld": 945,
        "actual_ld": 11.53,
    },
    "SCEN-03": {
        "bars": "5-T20",
        "clear_gap": 31.00,
        "ast": 1570.80,
        "d_actual": 527.0,
        "stirrup_spacing": 230.0,
        "ld": 880,
        "actual_ld": 11.39,
    },
    "SCEN-04": {
        "bars": "6-T16",
        "clear_gap": 25.60,
        "ast": 1206.37,
        "d_actual": 404.0,
        "stirrup_spacing": 300.0,
        "ld": 755,
        "actual_ld": 12.38,
    },
    "SCEN-05": {
        "bars": "3-T20",
        "clear_gap": 32.00,
        "ast": 942.48,
        "d_actual": 362.0,
        "stirrup_spacing": 270.0,
        "ld": 815,
        "actual_ld": 12.43,
    },
}

for sc in scenarios:
    sc_id = sc["scenario_id"]
    inputs = sc["inputs"]
    res = size_beam_from_loads(
        span_m=inputs["span_m"],
        dead_load_kN_per_m=inputs["dead_load_kN_per_m"],
        live_load_kN_per_m=inputs["live_load_kN_per_m"],
        fck=inputs["fck"],
        fy=inputs["fy"],
        exposure=inputs["exposure"],
    )
    rebar = res["reinforcement_detailing"]
    dims = res["section_dimensions"]
    defl = res["deflection"]
    ld = res["development_length"]

    n_bars = rebar["main_bar_count"]
    bar_dia = rebar["main_bar_dia_mm"]
    cover = dims["cover_mm"]
    b = dims["b"]
    stirrup_dia = rebar["stirrup_dia_mm"]
    clear_gap = (b - 2 * cover - 2 * stirrup_dia - n_bars * bar_dia) / (n_bars - 1)

    new_info = {
        "bars": f"{n_bars}-T{int(bar_dia)}",
        "clear_gap": round(clear_gap, 2),
        "ast": round(rebar["main_bar_area_provided_mm2"], 2),
        "d_actual": dims["d_actual"],
        "stirrup_spacing": rebar["stirrup_spacing_mm"],
        "ld": ld["ld_rounded_mm"],
        "actual_ld": round(defl["actual_ld_ratio"], 2),
    }

    print(f"Scenario: {sc_id}")
    print(f"  Old: {old_data[sc_id]}")
    print(f"  New: {new_info}")
