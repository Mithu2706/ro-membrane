"""Unit conversions. Canonical internal units:

flow m³/d, flux L/(m²·h) (LMH), pressure bar, concentration mg/L, temperature °C.
"""
from __future__ import annotations

PSI_TO_BAR = 0.0689475729
MPA_TO_BAR = 10.0
GPD_TO_M3D = 0.00378541178
GPM_TO_M3H = 0.227124707
FT2_TO_M2 = 0.09290304

# Molar masses (g/mol) used for "as CaCO3" conversions
CA_TO_CACO3 = 100.0869 / 40.078  # 2.497
MG_TO_CACO3 = 100.0869 / 24.305  # 4.118


def psi_to_bar(psi: float) -> float:
    return psi * PSI_TO_BAR


def bar_to_psi(bar: float) -> float:
    return bar / PSI_TO_BAR


def mpa_to_bar(mpa: float) -> float:
    return mpa * MPA_TO_BAR


def gpd_to_m3d(gpd: float) -> float:
    return gpd * GPD_TO_M3D


def gpm_to_m3h(gpm: float) -> float:
    return gpm * GPM_TO_M3H


def ft2_to_m2(ft2: float) -> float:
    return ft2 * FT2_TO_M2


def f_to_c(f: float) -> float:
    return (f - 32.0) * 5.0 / 9.0


def m3d_to_m3h(m3d: float) -> float:
    return m3d / 24.0


def m3h_to_m3d(m3h: float) -> float:
    return m3h * 24.0


def flux_lmh_from_flow(flow_m3d: float, area_m2: float) -> float:
    """Average flux (LMH) from permeate flow (m³/d) over membrane area (m²).

    1 m³/d = 1000 L / 24 h.
    """
    if area_m2 <= 0:
        raise ValueError("Membrane area must be positive")
    return flow_m3d * 1000.0 / 24.0 / area_m2


def flow_m3d_from_flux(flux_lmh: float, area_m2: float) -> float:
    """Permeate flow (m³/d) = Jw (L/m²/h) × Am (m²) × 24 h/d ÷ 1000 L/m³."""
    if area_m2 < 0:
        raise ValueError("Membrane area cannot be negative")
    return flux_lmh * area_m2 * 24.0 / 1000.0


def calcium_as_caco3(ca_mg_l: float) -> float:
    return ca_mg_l * CA_TO_CACO3


def magnesium_as_caco3(mg_mg_l: float) -> float:
    return mg_mg_l * MG_TO_CACO3
