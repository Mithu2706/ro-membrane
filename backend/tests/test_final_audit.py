"""Regression tests for the final targeted audit (see docs/AUDIT.md, section "Final audit")."""
import pytest

from app.engine.chemistry import GYPSUM_KSP_25C
from app.engine.hydraulics import concentration_factor_ideal
from app.engine.inputs import AssessmentInput
from app.engine.recommend import assess

from .test_engine import FULL_BW, bw_input, cand, make_membrane


def check(c, key):
    return next((x for x in c["checks"] if x["key"] == key), None)


def gypsum(res):
    return next(i for i in res["chemistry"]["items"] if i["key"] == "sulfate")


def sulfate_for_ratio(ratio, ca_mg_l=150.0, recovery=0.7):
    """Sulfate (mg/L) giving the requested ideal bulk-concentrate IAP/Ksp for the given calcium and recovery."""
    cf = concentration_factor_ideal(recovery)
    ca = ca_mg_l / 1000 / 40.078 * cf
    so4_mol = ratio * GYPSUM_KSP_25C / ca / cf
    return so4_mol * 96.06 * 1000


# --- 1. Calcium sulfate screen -----------------------------------------------------------------

def test_g1_ratio_just_below_saturation_is_unresolved_not_safe():
    r = assess(bw_input(chemistry={"calcium_mg_l": 150, "sulfate_mg_l": sulfate_for_ratio(0.95)}), [])
    g = gypsum(r)
    assert g["status"] == "not_assessed"
    assert "unresolved" in g["message"].lower()


def test_g1_low_ratio_is_low_with_screening_wording():
    r = assess(bw_input(chemistry={"calcium_mg_l": 150, "sulfate_mg_l": sulfate_for_ratio(0.2)}), [])
    g = gypsum(r)
    assert g["status"] == "ok"
    assert "screening" in g["message"].lower()
    assert "safe" not in g["message"].lower()


def test_g1_headroom_boundary():
    at = gypsum(assess(bw_input(chemistry={"calcium_mg_l": 150, "sulfate_mg_l": sulfate_for_ratio(0.249)}), []))
    over = gypsum(assess(bw_input(chemistry={"calcium_mg_l": 150, "sulfate_mg_l": sulfate_for_ratio(0.26)}), []))
    assert at["status"] == "ok" and over["status"] == "not_assessed"


def test_g1_concentration_basis_scales_with_cf_squared():
    so4 = sulfate_for_ratio(0.2, recovery=0.7)
    assert gypsum(assess(bw_input(chemistry={"calcium_mg_l": 150, "sulfate_mg_l": so4}), []))["status"] == "ok"
    # Same water at 85 % recovery: CF 3.33 -> 6.67, IAP x4 -> ratio 0.8 -> unresolved
    r = assess(bw_input(recovery_pct=85, chemistry={"calcium_mg_l": 150, "sulfate_mg_l": so4}), [])
    assert gypsum(r)["status"] == "not_assessed"


@pytest.mark.parametrize("temp", [3.0, 50.0])
def test_g2_outside_temperature_range_is_unresolved(temp):
    r = assess(bw_input(feed_temperature_c=temp, chemistry={"calcium_mg_l": 10, "sulfate_mg_l": 5}), [])
    g = gypsum(r)
    assert g["status"] == "not_assessed"
    assert "temperature" in g["message"].lower()


def test_gypsum_hardness_fallback_is_upper_bound():
    r = assess(bw_input(chemistry={"calcium_mg_l": None, "hardness_mg_l_caco3": 375, "sulfate_mg_l": 60}), [])
    assert "hardness" in gypsum(r)["detail"]


# --- 2. Feed-flow limits ---------------------------------------------------------------------------

def test_f1_feed_flow_above_limit_for_any_arrangement_fails():
    m = make_membrane(**{**FULL_BW, "max_feed_flow_m3h": 1.0})
    r = assess(bw_input(recovery_pct=10), [m])
    c = cand(r, 1)
    t = c["technical"]
    assert t["lead_feed_all_parallel_m3h"] > 1.0
    assert check(c, "arrangement")["status"] == "fail"
    assert c["status"] == "unsuitable"
    assert r["outcome"] == "no_supported_recommendation"


def test_f1_feed_flow_limit_undocumented_is_unknown():
    m = make_membrane(**{k: v for k, v in FULL_BW.items() if k != "max_feed_flow_m3h"})
    c = cand(assess(bw_input(), [m]), 1)
    chk = check(c, "arrangement")
    assert chk["status"] == "unknown"
    assert "maximum feed flow" in chk["message"]
    assert c["status"] == "conditional"


def test_minimum_concentrate_flow_undocumented_is_unknown():
    m = make_membrane(**{k: v for k, v in FULL_BW.items() if k != "min_concentrate_permeate_ratio"})
    chk = check(cand(assess(bw_input(), [m]), 1), "arrangement")
    assert chk["status"] == "unknown"
    assert "minimum concentrate flow" in chk["message"]


def test_no_uniform_arrangement_is_caution_not_failure():
    # Tight feed limit forces many parallel lines; ratio forces long series -> no uniform array of N elements
    m = make_membrane(**{**FULL_BW, "max_feed_flow_m3h": 3.0, "min_concentrate_permeate_ratio": 5})
    c = cand(assess(bw_input(), [m]), 1)
    assert check(c, "arrangement")["status"] == "warn"
    assert c["status"] == "conditional"


def test_arrangement_unknown_when_element_count_not_estimated():
    c = cand(assess(bw_input(design_flux_lmh=None), [make_membrane(**FULL_BW)]), 1)
    assert check(c, "arrangement")["status"] == "unknown"
    assert c["status"] != "suitable"


def test_seed_hydranautics_limits_enforced(membranes):
    """SWC4+ / ESPA-2540 carry verified Fmax and 5:1 ratio; FilmTec sheets carry Fmax only."""
    r = assess(AssessmentInput(application="bwro", feed_tds_mg_l=2500, feed_temperature_c=22, available_pressure_bar=16,
                               permeate_flow_m3d=1000, recovery_pct=70, design_flux_lmh=22,
                               chemistry={"ph": 7.2, "calcium_mg_l": 10, "alkalinity_mg_l_caco3": 20, "sdi": 2.5,
                                          "turbidity_ntu": 0.2, "silica_mg_l": 15, "sulfate_mg_l": 20,
                                          "oxidant_exposure": "none"}), membranes)
    espa = next(c for c in r["candidates"] if c["model"] == "ESPA-2540")
    bw = next(c for c in r["candidates"] if c["model"] == "BW30-400/34i")
    assert check(espa, "arrangement")["status"] in ("pass", "warn")
    assert check(bw, "arrangement")["status"] == "unknown"  # minimum concentrate flow not in the verified sheet


# --- 3. Element counts are membrane-level -------------------------------------------------------

def test_element_count_scope_is_stated():
    r = assess(bw_input(), [make_membrane(**FULL_BW)])
    assert any("membrane-level" in a and "not a plant configuration" in a for a in r["assumptions"])


# --- 4. Exclusion before ranking ------------------------------------------------------------------

def test_r1_system_hard_failure_applies_to_every_candidate():
    r = assess(bw_input(feed_flow_limit_m3d=1000), [make_membrane(1, **FULL_BW), make_membrane(2, **FULL_BW)])
    assert r["outcome"] == "no_supported_recommendation"
    for c in r["candidates"]:
        assert c["status"] == "unsuitable"
        assert check(c, "feed_flow_limit")["status"] == "fail"
        assert c["rank"] is None


def test_r2_only_viable_candidates_are_ranked():
    good = make_membrane(1, **FULL_BW)
    bad = make_membrane(2, **{**FULL_BW, "max_operating_pressure_bar": 5})
    unknown = make_membrane(3, **{k: v for k, v in FULL_BW.items() if k != "max_operating_temperature_c"})
    other = make_membrane(4, **{**FULL_BW, "rated_permeate_flow_m3d": 48})
    r = assess(bw_input(priority="quality"), [bad, unknown, good, other])
    ranks = {c["membrane_id"]: c["rank"] for c in r["candidates"]}
    assert ranks[2] is None and ranks[3] is None
    assert sorted(v for v in ranks.values() if v is not None) == [1, 2]
    assert r["recommended"]["rank"] == 1
    assert all(c["status"] in ("suitable", "conditional") for c in [r["recommended"], *r["alternatives"]])


def test_priority_cannot_promote_excluded_candidate():
    # Excluded candidate has the best permeate estimate but violates a pressure limit
    best_quality_bad = make_membrane(1, **{**FULL_BW, "rated_salt_rejection_pct": 99.95, "max_operating_pressure_bar": 5})
    ok = make_membrane(2, **FULL_BW)
    r = assess(bw_input(priority="quality"), [best_quality_bad, ok])
    assert r["recommended"]["membrane_id"] == 2
    assert cand(r, 1)["rank"] is None


def test_rated_point_reproduction_is_internally_consistent(membranes):
    """Circular consistency check (NOT validation): at the datasheet test point the engine must return the test pressure."""
    m = next(x for x in membranes if x.model == "SW30XLE-440")
    rated_flux = 37.4 / 41 * 1000 / 24
    inp = AssessmentInput(application="swro", feed_tds_mg_l=32000, feed_temperature_c=25, available_pressure_bar=80,
                          permeate_flow_m3d=37.4 * 10, recovery_pct=8, design_flux_lmh=rated_flux,
                          chemistry={"oxidant_exposure": "none"})
    t = assess(inp, [m])["candidates"][0]["technical"]
    assert t["elements_required"] == 10
    assert t["required_pressure_bar"] == pytest.approx(55.0, abs=1e-6)


def test_element_count_spread_is_reported_without_threshold():
    small = make_membrane(1, **FULL_BW)
    tiny = make_membrane(2, **{**FULL_BW, "active_area_m2": 2.37, "rated_permeate_flow_m3d": 2.84})
    r = assess(bw_input(), [small, tiny])
    viable = [c for c in r["candidates"] if c["rank"] is not None]
    assert len(viable) == 2
    w = next(x for x in r["warnings"] if x["title"] == "Element counts differ between candidates")
    counts = sorted(c["estimates"]["elements_required"] for c in viable)
    assert f"{counts[0]:,}" in w["message"] and f"{counts[1]:,}" in w["message"]
    # informational only: element count does not change status or exclude a candidate
    assert w["severity"] == "info"
