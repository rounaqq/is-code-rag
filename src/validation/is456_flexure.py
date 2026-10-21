"""
Deterministic IS 456:2000 Flexure Calculations for Singly Reinforced Rectangular Sections.
Annex G, G-1.1. Units: N, mm, N/mm2; moments in N*mm.
No formulas or limits from memory. Does NOT read .env.
"""

import math
from typing import Dict, Any

from src.validation.is456_checks import xu_max_over_d

CITATION_G1_1 = "IS 456:2000 Annex G, G-1.1"
FORMULA_TEXT_G1_1B = "Mu = 0.87*fy*Ast*d*(1 - Ast*fy/(b*d*fck))"


def mu_lim(b: float, d: float, fck: float, fy: float) -> float:
    """
    Computes limiting moment of resistance (Mu_lim in N*mm) for a singly reinforced rectangular section.
    Formula from G-1.1(c):
        Mu_lim = 0.36 * (xu_max/d) * (1 - 0.42 * (xu_max/d)) * b * d^2 * fck
    where (xu_max/d) is taken from Cl. 38.1 Note via xu_max_over_d(fy).

    Rejects zero or negative inputs with ValueError.
    For an unsupported fy, lets ValueError from xu_max_over_d come through.
    """
    if b is None or d is None or fck is None or fy is None:
        raise ValueError("Inputs cannot be None.")
    if isinstance(b, bool) or isinstance(d, bool) or isinstance(fck, bool) or isinstance(fy, bool):
        raise ValueError("Boolean inputs not allowed.")

    b_val = float(b)
    d_val = float(d)
    fck_val = float(fck)
    fy_val = float(fy)

    if b_val <= 0 or d_val <= 0 or fck_val <= 0 or fy_val <= 0:
        raise ValueError("All section dimensions, concrete strength, and steel yield strength must be positive.")

    # xu_max/d from Cl. 38.1 Note via xu_max_over_d(fy)
    xu_max_d = xu_max_over_d(fy_val)

    # G-1.1(c): Mu_lim = 0.36*(xu_max/d)*(1 - 0.42*(xu_max/d))*b*d^2*fck
    val = 0.36 * xu_max_d * (1.0 - 0.42 * xu_max_d) * b_val * (d_val ** 2) * fck_val
    return val


def ast_required_singly(b: float, d: float, fck: float, fy: float, mu: float) -> Dict[str, Any]:
    """
    Computes required tension steel area Ast (mm2) for a singly reinforced rectangular beam section
    under factored bending moment Mu (N*mm).
    Solves G-1.1(b):
        Mu = 0.87*fy*Ast*d*(1 - Ast*fy/(b*d*fck))
    as a quadratic in Ast:
        (0.87*fy^2 / (b*fck)) * Ast^2 - (0.87*fy*d) * Ast + Mu = 0
    taking the smaller root (under-reinforced solution).

    If Mu > Mu_lim or the discriminant is negative:
        returns status "needs_compression_steel" with no Ast.
    Otherwise:
        returns status "ok", ast_mm2, xu_over_d (from G-1.1(a)), mu_lim, citation, and formula.

    Rejects zero or negative inputs with ValueError.
    For an unsupported fy, lets ValueError from xu_max_over_d come through.
    """
    if b is None or d is None or fck is None or fy is None or mu is None:
        raise ValueError("Inputs cannot be None.")
    if (
        isinstance(b, bool)
        or isinstance(d, bool)
        or isinstance(fck, bool)
        or isinstance(fy, bool)
        or isinstance(mu, bool)
    ):
        raise ValueError("Boolean inputs not allowed.")

    b_val = float(b)
    d_val = float(d)
    fck_val = float(fck)
    fy_val = float(fy)
    mu_val = float(mu)

    if b_val <= 0 or d_val <= 0 or fck_val <= 0 or fy_val <= 0 or mu_val <= 0:
        raise ValueError("All section dimensions, material strengths, and bending moment must be strictly positive.")

    # 1. Compute limiting moment Mu_lim
    mu_lim_val = mu_lim(b=b_val, d=d_val, fck=fck_val, fy=fy_val)

    # 2. Quadratic coefficients: A * Ast^2 - B * Ast + Mu = 0
    a_coeff = (0.87 * (fy_val ** 2)) / (b_val * fck_val)
    b_coeff = 0.87 * fy_val * d_val
    discriminant = (b_coeff ** 2) - 4.0 * a_coeff * mu_val

    # Check if section exceeds singly reinforced limit or discriminant is negative
    if mu_val > mu_lim_val or discriminant < 0:
        return {
            "status": "needs_compression_steel",
            "ast_mm2": None,
            "mu_lim": mu_lim_val,
            "citation": CITATION_G1_1,
            "formula": FORMULA_TEXT_G1_1B,
            "formula_text": FORMULA_TEXT_G1_1B,
            "notes": "Applied moment exceeds limiting moment of resistance for singly reinforced section; compression steel required.",
        }

    # Smaller root (under-reinforced solution)
    ast_val = (b_coeff - math.sqrt(discriminant)) / (2.0 * a_coeff)

    # G-1.1(a): xu/d = 0.87*fy*Ast / (0.36*fck*b*d)
    xu_d = (0.87 * fy_val * ast_val) / (0.36 * fck_val * b_val * d_val)

    return {
        "status": "ok",
        "ast_mm2": ast_val,
        "xu_over_d": xu_d,
        "mu_lim": mu_lim_val,
        "citation": CITATION_G1_1,
        "formula": FORMULA_TEXT_G1_1B,
        "formula_text": FORMULA_TEXT_G1_1B,
    }
