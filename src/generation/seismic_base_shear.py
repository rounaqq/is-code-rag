"""
Deterministic Seismic Base Shear and Lateral Force Calculator per IS 1893 (Part 1):2016.

Step 6: Compliance Reasoning Engine / Deterministic Structural Calculations
Follows:
- Table 2: Zone Factor (Z)
- Table 6: Importance Factor (I)
- Table 7: Response Reduction Factor (R)
- Cl. 6.4.2 & Fig. 2: Spectral Acceleration Coefficient (Sa / g)
- Cl. 7.6.2: Approximate Fundamental Natural Period (Ta)
- Cl. 6.4.2: Design Horizontal Seismic Coefficient (Ah)
- Cl. 7.2.1: Total Design Base Shear (VB)
- Cl. 7.11.1: Storey Drift Limit (Delta <= 0.004 * hi)
"""

import math
from typing import Dict, Any, Optional, List


ZONE_FACTORS: Dict[str, float] = {
    "II": 0.10,
    "III": 0.16,
    "IV": 0.24,
    "V": 0.36,
}

IMPORTANCE_FACTORS: Dict[str, float] = {
    "hospital": 1.5,
    "school": 1.5,
    "emergency": 1.5,
    "dense_commercial": 1.2,
    "residential_dense": 1.2,
    "residential": 1.0,
    "office": 1.0,
    "general": 1.0,
}

RESPONSE_REDUCTION_FACTORS: Dict[str, float] = {
    "rc_smrf": 5.0,        # Special RC Moment-Resisting Frame (IS 13920 ductile)
    "rc_omrf": 3.0,        # Ordinary RC Moment-Resisting Frame (IS 456 standard)
    "steel_cbf": 4.0,      # Concentric Braced Steel Frame
    "steel_ebf": 4.5,      # Eccentric Braced Steel Frame
    "ductile_wall": 4.0,   # Ductile Shear Wall
}


def calculate_fundamental_period_ta(
    height_m: float,
    base_dim_m: Optional[float] = None,
    frame_type: str = "rc_bare_mrframe",
) -> Dict[str, Any]:
    """
    Computes approximate fundamental natural period Ta per IS 1893:2016 Cl. 7.6.2.
    """
    if height_m <= 0:
        raise ValueError("Building height must be strictly positive.")

    ft = frame_type.lower()
    if ft == "rc_bare_mrframe":
        # Cl. 7.6.2(a): Ta = 0.075 * h^0.75
        ta = 0.075 * math.pow(height_m, 0.75)
        citation = "IS 1893 (Part 1):2016 Cl. 7.6.2(a)"
        formula = "Ta = 0.075 * h^0.75"
    elif ft == "steel_bare_frame":
        # Cl. 7.6.2(b): Ta = 0.085 * h^0.75
        ta = 0.085 * math.pow(height_m, 0.75)
        citation = "IS 1893 (Part 1):2016 Cl. 7.6.2(b)"
        formula = "Ta = 0.085 * h^0.75"
    else:
        # Cl. 7.6.2(c): Ta = 0.09 * h / sqrt(d)
        d = base_dim_m if base_dim_m and base_dim_m > 0 else 10.0
        ta = (0.09 * height_m) / math.sqrt(d)
        citation = "IS 1893 (Part 1):2016 Cl. 7.6.2(c)"
        formula = "Ta = 0.09 * h / sqrt(d)"

    return {
        "ta_seconds": round(ta, 3),
        "citation": citation,
        "formula": formula,
    }


def calculate_spectral_acceleration_sa_over_g(
    ta: float,
    soil_type: str = "medium",
) -> Dict[str, Any]:
    """
    Computes design acceleration coefficient Sa / g for 5% damping per Cl. 6.4.2 & Fig. 2.
    """
    st = soil_type.lower()
    if "rock" in st or "hard" in st or st == "i":
        # Type I: Rock or Hard Soil
        soil_name = "Type I (Rock / Hard Soil)"
        if ta <= 0.10:
            sa_g = 1.0 + 15.0 * ta
        elif ta <= 0.40:
            sa_g = 2.50
        else:
            sa_g = min(2.50, 1.00 / ta)
    elif "soft" in st or st == "iii":
        # Type III: Soft Soil
        soil_name = "Type III (Soft Soil)"
        if ta <= 0.10:
            sa_g = 1.0 + 15.0 * ta
        elif ta <= 0.67:
            sa_g = 2.50
        else:
            sa_g = min(2.50, 1.67 / ta)
    else:
        # Type II: Medium Soil (Default)
        soil_name = "Type II (Medium Soil)"
        if ta <= 0.10:
            sa_g = 1.0 + 15.0 * ta
        elif ta <= 0.55:
            sa_g = 2.50
        else:
            sa_g = min(2.50, 1.36 / ta)

    return {
        "sa_over_g": round(sa_g, 3),
        "soil_type_name": soil_name,
        "citation": "IS 1893 (Part 1):2016 Cl. 6.4.2 & Fig. 2",
    }


def calculate_seismic_base_shear(
    height_m: float,
    total_weight_kN: float,
    base_dim_m: Optional[float] = None,
    seismic_zone: str = "IV",
    occupancy: str = "residential",
    structural_system: str = "rc_smrf",
    soil_type: str = "medium",
    frame_type: str = "rc_bare_mrframe",
    storey_height_m: float = 3.0,
) -> Dict[str, Any]:
    """
    Calculates design horizontal seismic coefficient Ah, total base shear VB,
    and storey drift serviceability limit.
    """
    zone_key = seismic_zone.upper()
    if zone_key not in ZONE_FACTORS:
        raise ValueError(f"Invalid seismic zone '{seismic_zone}'. Must be II, III, IV, or V.")

    z = ZONE_FACTORS[zone_key]
    i = IMPORTANCE_FACTORS.get(occupancy.lower(), 1.0)
    r = RESPONSE_REDUCTION_FACTORS.get(structural_system.lower(), 5.0)

    # Fundamental period
    ta_info = calculate_fundamental_period_ta(height_m=height_m, base_dim_m=base_dim_m, frame_type=frame_type)
    ta = ta_info["ta_seconds"]

    # Sa / g
    sa_info = calculate_spectral_acceleration_sa_over_g(ta=ta, soil_type=soil_type)
    sa_g = sa_info["sa_over_g"]

    # Design Horizontal Seismic Coefficient Ah = (Z / 2) * (I / R) * (Sa / g)
    ah = (z / 2.0) * (i / r) * sa_g

    # Minimum floor for short period: Ah >= Z / 2 when T <= 0.10 s
    if ta <= 0.10:
        ah = max(ah, z / 2.0)

    ah = round(ah, 4)

    # Total Design Base Shear VB = Ah * W
    vb_kN = round(ah * total_weight_kN, 2)

    # Storey Drift Limit: Delta <= 0.004 * hi (IS 1893 Cl. 7.11.1)
    drift_limit_mm = round(0.004 * storey_height_m * 1000.0, 1)

    return {
        "status": "SUCCESS",
        "inputs": {
            "building_height_m": height_m,
            "base_dimension_m": base_dim_m,
            "total_weight_kN": total_weight_kN,
            "seismic_zone": zone_key,
            "occupancy": occupancy,
            "structural_system": structural_system,
            "soil_type": soil_type,
        },
        "seismic_parameters": {
            "zone_factor_Z": z,
            "importance_factor_I": i,
            "response_reduction_factor_R": r,
            "fundamental_period_Ta_sec": ta,
            "spectral_acceleration_Sa_g": sa_g,
            "horizontal_seismic_coefficient_Ah": ah,
        },
        "design_base_shear_VB_kN": vb_kN,
        "base_shear_ratio": round(ah * 100.0, 2),  # VB as % of W
        "drift_limitations": {
            "max_allowable_storey_drift_mm": drift_limit_mm,
            "formula": "Delta <= 0.004 * hi",
            "citation": "IS 1893 (Part 1):2016 Cl. 7.11.1",
        },
        "citations": [
            f"IS 1893 (Part 1):2016 Table 2 (Zone {zone_key} Factor Z = {z})",
            f"IS 1893 (Part 1):2016 Table 6 (Importance Factor I = {i})",
            f"IS 1893 (Part 1):2016 Table 7 (Response Reduction R = {r})",
            ta_info["citation"],
            sa_info["citation"],
            "IS 1893 (Part 1):2016 Cl. 6.4.2 (Ah = (Z/2) * (I/R) * (Sa/g))",
            "IS 1893 (Part 1):2016 Cl. 7.2.1 (VB = Ah * W)",
            "IS 1893 (Part 1):2016 Cl. 7.11.1 (Storey Drift)",
        ],
    }


def calculate_vertical_distribution_of_base_shear(
    vb_kN: float,
    floor_weights_kN: List[float],
    floor_heights_m: List[float],
) -> Dict[str, Any]:
    """
    Computes floor-by-floor lateral design seismic forces Qi and cumulative storey shear Vi
    per IS 1893 (Part 1):2016 Cl. 7.6.3:
        Qi = VB * (Wi * hi^2) / sum(Wj * hj^2)
        Vi = sum_{j=i}^n Qj
    """
    if len(floor_weights_kN) != len(floor_heights_m):
        raise ValueError("floor_weights_kN and floor_heights_m must have identical length.")
    if len(floor_weights_kN) == 0:
        raise ValueError("At least one floor level is required.")

    n = len(floor_weights_kN)
    wi_hi_sq = [w * (h ** 2) for w, h in zip(floor_weights_kN, floor_heights_m)]
    sum_wi_hi_sq = sum(wi_hi_sq)

    if sum_wi_hi_sq <= 0:
        raise ValueError("Sum of (Wi * hi^2) must be strictly positive.")

    lateral_forces_Qi: List[float] = []
    for wh2 in wi_hi_sq:
        qi = vb_kN * (wh2 / sum_wi_hi_sq)
        lateral_forces_Qi.append(round(qi, 2))

    # Calculate cumulative storey shear Vi from roof down to base
    storey_shears_Vi: List[float] = [0.0] * n
    running_shear = 0.0
    for i in range(n - 1, -1, -1):
        running_shear += lateral_forces_Qi[i]
        storey_shears_Vi[i] = round(running_shear, 2)

    floors_data = []
    for i in range(n):
        floors_data.append({
            "floor_level": i + 1,
            "height_above_base_m": floor_heights_m[i],
            "seismic_weight_Wi_kN": floor_weights_kN[i],
            "lateral_force_Qi_kN": lateral_forces_Qi[i],
            "storey_shear_Vi_kN": storey_shears_Vi[i],
        })

    return {
        "status": "SUCCESS",
        "total_base_shear_VB_kN": vb_kN,
        "sum_lateral_forces_kN": round(sum(lateral_forces_Qi), 2),
        "floors": floors_data,
        "formula": "Qi = VB * (Wi * hi^2) / sum(Wj * hj^2)",
        "citation": "IS 1893 (Part 1):2016 Cl. 7.6.3",
    }
