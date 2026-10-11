"""Core RO relations: flow balance, rejection, osmotic pressure, flux.

All functions are pure and documented with their assumptions. They are the
building blocks for the single-element-equivalent screening model used by the
recommendation engine; vessel / multi-stage models can be layered on later.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .units import flow_m3d_from_flux

R_BAR_L_PER_MOL_K = 0.0831446  # universal gas constant, L·bar/(mol·K)
NACL_MOLAR_MASS = 58.443  # g/mol
NACL_VANT_HOFF_I = 2.0


@dataclass(frozen=True)
class FlowBalance:
    permeate_m3d: float
    feed_m3d: float
    concentrate_m3d: float
    recovery: float  # fraction

    @property
    def closure_error(self) -> float:
        return self.feed_m3d - (self.permeate_m3d + self.concentrate_m3d)


def validate_recovery(recovery_fraction: float) -> None:
    if recovery_fraction is None or math.isnan(recovery_fraction):
        raise ValueError("Recovery is required")
    if not 0.0 < recovery_fraction < 1.0:
        raise ValueError("Recovery must be greater than 0% and less than 100%")


def flow_balance(permeate_m3d: float, recovery_fraction: float) -> FlowBalance:
    """Qf = Qp / r ;  Qc = Qf − Qp."""
    validate_recovery(recovery_fraction)
    if permeate_m3d <= 0:
        raise ValueError("Permeate flow must be positive")
    feed = permeate_m3d / recovery_fraction
    return FlowBalance(permeate_m3d=permeate_m3d, feed_m3d=feed, concentrate_m3d=feed - permeate_m3d,
                       recovery=recovery_fraction)


def salt_rejection_pct(feed_mg_l: float, permeate_mg_l: float) -> float:
    """R = 100 × (1 − Cp/Cf). Cf and Cp must be comparable concentrations."""
    if feed_mg_l <= 0:
        raise ValueError("Feed concentration must be positive")
    if permeate_mg_l < 0:
        raise ValueError("Permeate concentration cannot be negative")
    return 100.0 * (1.0 - permeate_mg_l / feed_mg_l)


def permeate_concentration(feed_mg_l: float, rejection_pct: float) -> float:
    """Rough estimate Cp ≈ Cf × (1 − R/100). Not valid ion-by-ion."""
    if not 0.0 <= rejection_pct <= 100.0:
        raise ValueError("Rejection must be between 0 and 100%")
    if feed_mg_l < 0:
        raise ValueError("Feed concentration cannot be negative")
    return feed_mg_l * (1.0 - rejection_pct / 100.0)


def concentration_factor_ideal(recovery_fraction: float) -> float:
    """CF = 1 / (1 − r), assuming complete salt rejection (idealised)."""
    validate_recovery(recovery_fraction)
    return 1.0 / (1.0 - recovery_fraction)


def concentrate_concentration_mass_balance(feed_mg_l: float, permeate_mg_l: float, recovery_fraction: float) -> float:
    """Cc = (Cf − r·Cp) / (1 − r): idealised steady-state solute mass balance.

    Ignores precipitation, CP and changing rejection along the vessel.
    """
    validate_recovery(recovery_fraction)
    return (feed_mg_l - recovery_fraction * permeate_mg_l) / (1.0 - recovery_fraction)


def osmotic_pressure_bar(tds_mg_l: float, temperature_c: float) -> float:
    """Ideal van 't Hoff osmotic pressure treating TDS as NaCl (i = 2, φ = 1).

    π = i · (C / M) · R · T. This NaCl-equivalent approximation slightly over-
    estimates π for NaCl at seawater strength (osmotic coefficient < 1) and can be
    materially wrong for mixed or multivalent-ion waters. It is a screening value,
    not a design correlation (see Nayar et al., 2016 for validated correlations).
    """
    if tds_mg_l < 0:
        raise ValueError("TDS cannot be negative")
    molar = tds_mg_l / 1000.0 / NACL_MOLAR_MASS  # mol/L
    return NACL_VANT_HOFF_I * molar * R_BAR_L_PER_MOL_K * (temperature_c + 273.15)


def water_flux_lmh(permeance_lmh_bar: float, delta_p_bar: float, delta_pi_bar: float) -> float:
    """Solution-diffusion baseline Jw = A × (ΔP − Δπ). Negative NDP gives zero forward flux."""
    return max(0.0, permeance_lmh_bar * (delta_p_bar - delta_pi_bar))


def permeate_flow_m3d(flux_lmh: float, area_m2: float) -> float:
    """Qp = Jw × Am (with LMH → m³/d conversion)."""
    return flow_m3d_from_flux(flux_lmh, area_m2)


def permeance_from_rating(flux_lmh: float, test_pressure_bar: float, test_avg_osmotic_bar: float) -> float | None:
    """Back-calculate an apparent water permeance A from a rated test point.

    A = J / (P_test − π_avg,test). Neglects CP, permeate osmotic pressure and
    element pressure drop, so it is an *apparent* value for screening only.
    Returns None if the net driving pressure is not positive.
    """
    ndp = test_pressure_bar - test_avg_osmotic_bar
    if ndp <= 0 or flux_lmh <= 0:
        return None
    return flux_lmh / ndp


def average_feed_side_concentration(feed_mg_l: float, recovery_fraction: float) -> float:
    """Arithmetic mean of feed and idealised concentrate concentration."""
    return 0.5 * (feed_mg_l + feed_mg_l * concentration_factor_ideal(recovery_fraction))


def required_feed_pressure_bar(design_flux_lmh: float, permeance_lmh_bar: float, avg_osmotic_bar: float,
                               concentrate_osmotic_bar: float, pressure_loss_bar: float = 0.0) -> float:
    """Indicative feed pressure to reach a design average flux.

    P ≈ max(J/A + π_avg, π_conc) + losses. The second term enforces that the
    concentrate end still has positive net driving pressure.
    """
    if permeance_lmh_bar <= 0:
        raise ValueError("Permeance must be positive")
    return max(design_flux_lmh / permeance_lmh_bar + avg_osmotic_bar, concentrate_osmotic_bar) + pressure_loss_bar
