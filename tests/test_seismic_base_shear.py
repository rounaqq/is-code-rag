"""
Unit tests for Step 6 Seismic Base Shear Calculator per IS 1893 (Part 1):2016.
Validates fundamental period Ta, Sa/g, Ah, and base shear VB calculations.
"""

import pytest
from src.generation.seismic_base_shear import (
    calculate_fundamental_period_ta,
    calculate_spectral_acceleration_sa_over_g,
    calculate_seismic_base_shear,
    ZONE_FACTORS,
    IMPORTANCE_FACTORS,
    RESPONSE_REDUCTION_FACTORS,
)


def test_fundamental_period_bare_rc_frame():
    """Validates IS 1893:2016 Cl. 7.6.2(a): Ta = 0.075 * h^0.75 for bare RC frame."""
    # For h = 15.0 m (5-storey building): Ta = 0.075 * (15)^0.75 = 0.075 * 7.622 = 0.572 s
    res = calculate_fundamental_period_ta(height_m=15.0, frame_type="rc_bare_mrframe")
    assert 0.56 <= res["ta_seconds"] <= 0.58
    assert "Cl. 7.6.2(a)" in res["citation"]


def test_fundamental_period_infill_frame():
    """Validates IS 1893:2016 Cl. 7.6.2(c): Ta = 0.09 * h / sqrt(d) for infill frame."""
    # For h = 15.0 m, d = 9.0 m: Ta = 0.09 * 15 / 3 = 0.45 s
    res = calculate_fundamental_period_ta(height_m=15.0, base_dim_m=9.0, frame_type="rc_infill_frame")
    assert res["ta_seconds"] == 0.45
    assert "Cl. 7.6.2(c)" in res["citation"]


def test_spectral_acceleration_medium_soil_plateau():
    """Validates Sa/g = 2.50 for 0.10 < T <= 0.55 s in Type II medium soil."""
    res = calculate_spectral_acceleration_sa_over_g(ta=0.35, soil_type="medium")
    assert res["sa_over_g"] == 2.50


def test_spectral_acceleration_medium_soil_descending():
    """Validates Sa/g = 1.36 / T for T > 0.55 s in Type II medium soil."""
    # For T = 1.0 s: Sa/g = 1.36
    res = calculate_spectral_acceleration_sa_over_g(ta=1.0, soil_type="medium")
    assert res["sa_over_g"] == 1.36


def test_seismic_base_shear_zone_iv_hospital():
    """
    Validates complete IS 1893:2016 base shear calculation:
    Zone IV (Z=0.24), Hospital (I=1.5), SMRF (R=5.0), Medium soil, W = 10,000 kN, h = 15 m.
    """
    res = calculate_seismic_base_shear(
        height_m=15.0,
        total_weight_kN=10000.0,
        seismic_zone="IV",
        occupancy="hospital",
        structural_system="rc_smrf",
        soil_type="medium",
        storey_height_m=3.0,
    )
    assert res["status"] == "SUCCESS"
    assert res["seismic_parameters"]["zone_factor_Z"] == 0.24
    assert res["seismic_parameters"]["importance_factor_I"] == 1.5
    assert res["seismic_parameters"]["response_reduction_factor_R"] == 5.0

    # Ah must be strictly positive and reasonable (typically 0.04 to 0.15)
    ah = res["seismic_parameters"]["horizontal_seismic_coefficient_Ah"]
    assert 0.03 <= ah <= 0.15

    # VB = Ah * W
    assert res["design_base_shear_VB_kN"] > 0
    assert abs(res["design_base_shear_VB_kN"] - round(ah * 10000.0, 2)) < 0.1

    # Storey drift limit = 0.004 * 3000 mm = 12.0 mm
    assert res["drift_limitations"]["max_allowable_storey_drift_mm"] == 12.0


def test_vertical_distribution_of_base_shear():
    """
    Validates IS 1893:2016 Cl. 7.6.3: Qi = VB * (Wi * hi^2) / sum(Wj * hj^2).
    4-storey building: VB = 500 kN, floors at 3m, 6m, 9m, 12m with weights 3000, 3000, 3000, 2000 kN.
    """
    from src.generation.seismic_base_shear import calculate_vertical_distribution_of_base_shear

    weights = [3000.0, 3000.0, 3000.0, 2000.0]
    heights = [3.0, 6.0, 9.0, 12.0]
    vb = 500.0

    res = calculate_vertical_distribution_of_base_shear(
        vb_kN=vb,
        floor_weights_kN=weights,
        floor_heights_m=heights,
    )

    assert res["status"] == "SUCCESS"
    assert len(res["floors"]) == 4

    # Sum of lateral forces must equal total base shear VB
    sum_qi = sum(f["lateral_force_Qi_kN"] for f in res["floors"])
    assert abs(sum_qi - vb) <= 1.0

    # Storey shear at base (floor 1) must equal total base shear
    assert abs(res["floors"][0]["storey_shear_Vi_kN"] - vb) <= 1.0

    # Forces must increase quadratically with height: top floor carries higher lateral force than bottom
    assert res["floors"][3]["lateral_force_Qi_kN"] > res["floors"][0]["lateral_force_Qi_kN"]
