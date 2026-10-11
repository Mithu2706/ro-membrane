"""Code-correctness tests for unit conversions and core RO relations.

These confirm the equations are implemented as documented. They do NOT validate
the model against experimental RO performance.
"""
import math

import pytest

from app.engine import hydraulics as h
from app.engine import units as u
from app.engine.chemistry import langelier_index


# Unit conversions ---------------------------------------------------------------

def test_pressure_conversions():
    assert u.psi_to_bar(600) == pytest.approx(41.37, abs=0.01)
    assert u.psi_to_bar(225) == pytest.approx(15.51, abs=0.01)
    assert u.bar_to_psi(u.psi_to_bar(800)) == pytest.approx(800)
    assert u.mpa_to_bar(8.27) == pytest.approx(82.7)


def test_flow_and_area_conversions():
    assert u.gpd_to_m3d(10500) == pytest.approx(39.75, abs=0.01)  # datasheet states 40 m³/d
    assert u.gpd_to_m3d(6500) == pytest.approx(24.6, abs=0.01)
    assert u.ft2_to_m2(400) == pytest.approx(37.16, abs=0.01)
    assert u.gpm_to_m3h(85) == pytest.approx(19.3, abs=0.05)
    assert u.m3d_to_m3h(24) == 1
    assert u.f_to_c(77) == pytest.approx(25)


def test_flux_flow_roundtrip():
    # 40 m³/d over 37 m² = 45.05 LMH
    j = u.flux_lmh_from_flow(40, 37)
    assert j == pytest.approx(40000 / 24 / 37)
    assert u.flow_m3d_from_flux(j, 37) == pytest.approx(40)
    with pytest.raises(ValueError):
        u.flux_lmh_from_flow(10, 0)


def test_hardness_conversion():
    assert u.calcium_as_caco3(40.078) == pytest.approx(100.087, rel=1e-4)
    assert u.magnesium_as_caco3(24.305) == pytest.approx(100.087, rel=1e-4)


# Flow balance --------------------------------------------------------------------

@pytest.mark.parametrize("bad", [0, 0.0, 1.0, 1.5, -0.2, float("nan")])
def test_invalid_recovery_rejected(bad):
    with pytest.raises(ValueError):
        h.flow_balance(1000, bad)


def test_zero_permeate_rejected():
    with pytest.raises(ValueError):
        h.flow_balance(0, 0.5)


@pytest.mark.parametrize("qp,r", [(1000, 0.75), (5000, 0.45), (12.5, 0.10), (250000, 0.85), (1, 0.999)])
def test_flow_balance_identity(qp, r):
    fb = h.flow_balance(qp, r)
    assert fb.feed_m3d == pytest.approx(qp / r)
    assert fb.feed_m3d == pytest.approx(fb.permeate_m3d + fb.concentrate_m3d, rel=1e-12)
    assert abs(fb.closure_error) < 1e-9 * fb.feed_m3d
    assert fb.permeate_m3d / fb.feed_m3d == pytest.approx(r)


# Rejection and concentrations ------------------------------------------------------

def test_salt_rejection():
    assert h.salt_rejection_pct(2000, 10) == pytest.approx(99.5)
    assert h.salt_rejection_pct(35000, 35000) == 0
    with pytest.raises(ValueError):
        h.salt_rejection_pct(0, 1)
    with pytest.raises(ValueError):
        h.salt_rejection_pct(100, -1)


def test_permeate_concentration_inverse_of_rejection():
    cp = h.permeate_concentration(2000, 99.5)
    assert cp == pytest.approx(10)
    assert h.salt_rejection_pct(2000, cp) == pytest.approx(99.5)
    with pytest.raises(ValueError):
        h.permeate_concentration(2000, 101)


def test_concentration_factor_and_mass_balance():
    assert h.concentration_factor_ideal(0.75) == pytest.approx(4)
    # With zero salt passage, mass balance equals the ideal CF
    assert h.concentrate_concentration_mass_balance(1000, 0, 0.75) == pytest.approx(4000)
    # Solute mass is conserved: Qf·Cf = Qp·Cp + Qc·Cc
    cf, cp, r = 2500, 25, 0.7
    cc = h.concentrate_concentration_mass_balance(cf, cp, r)
    fb = h.flow_balance(100, r)
    assert fb.feed_m3d * cf == pytest.approx(fb.permeate_m3d * cp + fb.concentrate_m3d * cc)


def test_osmotic_pressure_magnitude():
    # Ideal van 't Hoff, NaCl-equivalent: ~0.85 bar per 1000 mg/L at 25 °C
    assert h.osmotic_pressure_bar(1000, 25) == pytest.approx(0.848, abs=0.005)
    assert h.osmotic_pressure_bar(0, 25) == 0
    assert h.osmotic_pressure_bar(35000, 25) > h.osmotic_pressure_bar(35000, 10)
    with pytest.raises(ValueError):
        h.osmotic_pressure_bar(-1, 25)


def test_water_flux_and_permeate_flow():
    assert h.water_flux_lmh(2.0, 15, 5) == pytest.approx(20)
    assert h.water_flux_lmh(2.0, 5, 15) == 0  # no forward flux below osmotic pressure
    # 20 LMH × 37 m² = 17.76 m³/d
    assert h.permeate_flow_m3d(20, 37) == pytest.approx(17.76)


def test_permeance_and_required_pressure_consistency():
    a = h.permeance_from_rating(45.0, 15.5, 1.8)
    assert a == pytest.approx(45 / 13.7)
    assert h.permeance_from_rating(10, 5, 6) is None
    # Required pressure reproduces the rating when evaluated at the test point
    p = h.required_feed_pressure_bar(45.0, a, 1.8, 0.0)
    assert p == pytest.approx(15.5)
    # Concentrate osmotic floor dominates when larger
    assert h.required_feed_pressure_bar(1.0, a, 1.8, 30.0, 2.0) == pytest.approx(32.0)


def test_langelier_index():
    lsi = langelier_index(7.5, 500, 25, 200, 150)
    assert lsi is not None and -1 < lsi < 1.5
    assert langelier_index(7.5, 500, 25, 0, 150) is None
    # Concentrating Ca and alkalinity raises the LSI
    assert langelier_index(7.5, 2000, 25, 800, 600) > lsi
