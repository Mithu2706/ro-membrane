"""Regression tests for defects confirmed in the 2026-10-10 audit.

Each test reproduces a defect that existed before the fix (see docs/AUDIT.md).
"""
import pytest

from app.engine.evidence import MembraneEvidence, ParamValue, is_ambiguous_conflict, resolve_parameters
from app.engine.hydraulics import flow_balance
from app.engine.inputs import AssessmentInput
from app.engine.recommend import assess, client_view

from .test_engine import FULL_BW, bw_input, cand, make_membrane

MR, V, R = "manufacturer-rated", "verified", "report-extracted"


def membrane_from_rows(rows, category="BWRO", apps=("bwro",)) -> MembraneEvidence:
    chosen, conflicts = resolve_parameters(rows)
    return MembraneEvidence(id=1, manufacturer="TestCo", model="T-1", category=category, intended_applications=list(apps),
                            params=chosen, conflicts=conflicts)


def rows(overrides=None, drop=(), extra=()):
    base = {**FULL_BW, **(overrides or {})}
    out = [ParamValue(k, v, "", MR, V, 1) for k, v in base.items() if k not in drop]
    return out + list(extra)


def check(c, key):
    return next((x for x in c["checks"] if x["key"] == key), None)


def test_baseline_is_suitable():
    assert cand(assess(bw_input(), [make_membrane(**FULL_BW)]), 1)["status"] == "suitable"


# --- Priority 1: critical unknowns, limits and conflicting sources -------------------------

def test_d1_turbidity_without_documented_limit_is_not_a_pass():
    r = assess(bw_input(chemistry={"sdi": None, "turbidity_ntu": 5.0}), [make_membrane(**FULL_BW)])
    c = cand(r, 1)
    assert check(c, "particulates")["status"] == "unknown"
    assert c["status"] != "suitable"


def test_d1_documented_turbidity_limit_requires_a_measurement():
    m = make_membrane(**{**FULL_BW, "max_feed_turbidity_ntu": 1.0})
    c = cand(assess(bw_input(), [m]), 1)  # SDI given, turbidity not measured
    assert check(c, "particulates")["status"] == "unknown"
    assert c["status"] == "conditional"


def test_d1_sdi_above_all_datasheets_with_undocumented_limit_blocks_recommendation():
    m = make_membrane(**{k: v for k, v in FULL_BW.items() if k != "max_feed_sdi"})
    r = assess(bw_input(chemistry={"sdi": 6.5}), [m])
    assert cand(r, 1)["status"] == "insufficient_evidence"
    assert r["outcome"] == "no_supported_recommendation"


def test_d2_chloramine_is_not_treated_as_safe():
    c = cand(assess(bw_input(chemistry={"oxidant_exposure": "chloramine"}), [make_membrane(**FULL_BW)]), 1)
    assert check(c, "oxidant")["status"] == "warn"
    assert c["status"] == "conditional"


def test_unknown_chlorine_exposure_is_never_suitable():
    c = cand(assess(bw_input(chemistry={"oxidant_exposure": "unknown"}), [make_membrane(**FULL_BW)]), 1)
    assert check(c, "oxidant")["status"] == "unknown"
    assert c["status"] != "suitable"


def test_undocumented_chlorine_tolerance_is_not_a_pass():
    m = make_membrane(**{k: v for k, v in FULL_BW.items() if k != "max_free_chlorine_mg_l"})
    c = cand(assess(bw_input(), [m]), 1)
    assert check(c, "oxidant")["status"] == "unknown"
    assert c["status"] != "suitable"


def test_d4_disputed_only_limit_is_treated_as_missing():
    m = membrane_from_rows(rows(drop=("max_operating_pressure_bar",),
                                extra=[ParamValue("max_operating_pressure_bar", 41, "bar", MR, "disputed", 1)]))
    assert m.get("max_operating_pressure_bar") is None
    c = cand(assess(bw_input(), [m]), 1)
    assert check(c, "pressure_rating")["status"] == "unknown"
    assert c["status"] == "insufficient_evidence"


@pytest.mark.parametrize("evidence", ["calculated", "estimated", "laboratory-experimental", "pilot-plant"])
def test_d5_non_rated_values_never_satisfy_limits(evidence):
    m = membrane_from_rows(rows(drop=("max_operating_pressure_bar",),
                                extra=[ParamValue("max_operating_pressure_bar", 41, "bar", evidence, V, 1)]))
    assert cand(assess(bw_input(), [m]), 1)["status"] == "insufficient_evidence"


def test_d6_equally_verified_conflicting_limit_blocks_suitability():
    m = membrane_from_rows(rows(extra=[ParamValue("max_operating_pressure_bar", 14, "bar", MR, V, 2)]))
    assert is_ambiguous_conflict(m.conflicts["max_operating_pressure_bar"])
    r = assess(bw_input(), [m])
    c = cand(r, 1)
    assert check(c, "source_conflict")["status"] == "unknown"
    assert c["status"] == "insufficient_evidence"
    assert r["outcome"] == "no_supported_recommendation"


def test_conflict_resolved_by_verification_is_conditional_and_uses_verified_value():
    m = membrane_from_rows(rows(extra=[ParamValue("max_operating_pressure_bar", 14, "bar", MR, R, 2)]))
    assert m.num("max_operating_pressure_bar") == 41
    assert not is_ambiguous_conflict(m.conflicts["max_operating_pressure_bar"])
    c = cand(assess(bw_input(), [m]), 1)
    assert check(c, "source_conflict")["status"] == "warn"
    assert c["status"] == "conditional"
    assert c["conflicts"] == ["max_operating_pressure_bar"]


def test_limit_violation_still_fails_when_other_data_complete():
    m = make_membrane(**{**FULL_BW, "max_operating_pressure_bar": 10})
    c = cand(assess(bw_input(), [m]), 1)
    assert check(c, "pressure_rating")["status"] == "fail"
    assert c["status"] == "unsuitable"


def test_pretreatment_does_not_clear_scaling_risk():
    chem = {"calcium_mg_l": 200, "alkalinity_mg_l_caco3": 300}
    without = cand(assess(bw_input(chemistry=chem), [make_membrane(**FULL_BW)]), 1)
    with_pt = cand(assess(bw_input(chemistry={**chem, "pretreatment": ["Antiscalant", "Acid dosing", "Softening"]}),
                          [make_membrane(**FULL_BW)]), 1)
    assert check(without, "chemistry")["status"] == "warn"
    assert check(with_pt, "chemistry")["status"] == "warn"
    assert with_pt["status"] == without["status"] == "conditional"


# --- Priority 2: engineering consistency ---------------------------------------------------

def test_d7_low_production_flags_oversized_element_and_uses_implied_flux():
    m = make_membrane(**{k: v for k, v in FULL_BW.items() if k != "min_concentrate_permeate_ratio"})
    r = assess(bw_input(permeate_flow_m3d=5, recovery_pct=50), [m])
    c = r["candidates"][0]
    assert c["estimates"]["elements_required"] == 1
    assert check(c, "element_sizing")["status"] == "warn"
    # pressure is evaluated at the flux the single element would actually run at
    assert c["technical"]["pressure_basis_flux_lmh"] == pytest.approx(5 * 1000 / 24 / 37)
    # no documented concentrate limit -> arrangement only partly checked
    assert check(c, "arrangement")["status"] == "unknown"
    assert c["status"] == "conditional"


def test_d7_documented_per_element_recovery_limit():
    m = make_membrane(**FULL_BW)  # ratio 5 -> max 16.7 % recovery per element
    c = cand(assess(bw_input(permeate_flow_m3d=5, recovery_pct=50), [m]), 1)
    assert check(c, "arrangement")["status"] == "warn"
    big = cand(assess(bw_input(), [m]), 1)  # 52 elements: 7 x 7 uniform array meets both limits
    assert check(big, "arrangement")["status"] == "pass"


def test_element_count_and_implied_flux_are_consistent():
    r = assess(bw_input(), [make_membrane(**FULL_BW)])
    t = r["candidates"][0]["technical"]
    n = t["elements_required"]
    # N elements at the implied flux deliver exactly the requested production
    assert n * 37 * t["implied_flux_lmh"] * 24 / 1000 == pytest.approx(1000)
    assert t["implied_flux_lmh"] <= 22 + 1e-9
    assert (n - 1) * t["permeate_per_element_m3d"] < 1000 <= n * t["permeate_per_element_m3d"]


def test_pressure_margin_is_relative_to_available_pressure():
    # Margin documented as "within 10% of available pressure". Choose P_avail so that
    # (P_avail - P_req)/P_avail = 9.5% (marginal) while (P_avail - P_req)/P_req = 10.5% (the old, wrong basis).
    t = assess(bw_input(), [make_membrane(**FULL_BW)])["candidates"][0]["technical"]
    p_req, p_high = t["required_pressure_bar"], t["required_pressure_high_bar"]
    pav = p_req / 0.905
    assert p_high < pav  # so only the margin rule can trigger the caution
    c = cand(assess(bw_input(available_pressure_bar=pav), [make_membrane(**FULL_BW)]), 1)
    assert check(c, "pressure_available")["status"] == "warn"


def test_boron_estimate_uses_average_feed_side_concentration():
    m = make_membrane(category="SWRO", apps=("swro",), **{**FULL_BW, "boron_rejection_pct": 90,
                                                           "max_operating_pressure_bar": 83})
    inp = AssessmentInput(application="swro", feed_tds_mg_l=35000, feed_temperature_c=25, available_pressure_bar=80,
                          permeate_flow_m3d=1000, recovery_pct=50, design_flux_lmh=14, target_boron_mg_l=1.0,
                          chemistry={"boron_mg_l": 5.0, "oxidant_exposure": "none"})
    c = cand(assess(inp, [m]), 1)
    # CF = 2 -> average boron 7.5 mg/L -> 0.75 mg/L at 90% rejection (feed-only basis would give 0.5)
    assert c["estimates"]["boron_permeate_mg_l"] == pytest.approx(0.75)


@pytest.mark.parametrize("qp,r", [(5, 0.5), (1000, 0.7), (5000, 0.45)])
def test_mass_balance_closure_for_engine_cases(qp, r):
    fb = flow_balance(qp, r)
    assert fb.feed_m3d == pytest.approx(fb.permeate_m3d + fb.concentrate_m3d)


# --- Priority 3: water chemistry --------------------------------------------------------------

def test_d3_unmeasured_sulfate_is_explicit_and_consistent_with_measured_low_sulfate():
    no_so4 = assess(bw_input(chemistry={"sulfate_mg_l": None}), [make_membrane(**FULL_BW)])
    low_so4 = assess(bw_input(chemistry={"sulfate_mg_l": 5}), [make_membrane(**FULL_BW)])
    item = lambda res: next(i for i in res["chemistry"]["items"] if i["key"] == "sulfate")["status"]  # noqa: E731
    assert item(no_so4) == "missing"
    assert item(low_so4) == "ok"
    # Measuring more must never make the outcome look worse than not measuring at all
    assert cand(low_so4, 1)["status"] == "suitable"
    assert cand(no_so4, 1)["status"] == "conditional"


def test_gypsum_screen_inconclusive_at_seawater_sulfate():
    inp = AssessmentInput(application="swro", feed_tds_mg_l=35000, feed_temperature_c=25, available_pressure_bar=70,
                          permeate_flow_m3d=1000, recovery_pct=45,
                          chemistry={"calcium_mg_l": 410, "sulfate_mg_l": 2700, "oxidant_exposure": "none"})
    item = next(i for i in assess(inp, [])["chemistry"]["items"] if i["key"] == "sulfate")
    assert item["status"] == "not_assessed"


def test_d9_ions_exceeding_tds_flagged():
    c = cand(assess(bw_input(chemistry={"sodium_mg_l": 5000, "chloride_mg_l": 6000}), [make_membrane(**FULL_BW)]), 1)
    assert check(c, "chemistry")["status"] == "warn"
    assert c["status"] == "conditional"


def test_d9_ion_imbalance_flagged():
    chem = {"calcium_mg_l": 60, "magnesium_mg_l": 25, "sodium_mg_l": 750, "chloride_mg_l": 300, "sulfate_mg_l": 50,
            "alkalinity_mg_l_caco3": 120}
    r = assess(bw_input(chemistry=chem), [make_membrane(**FULL_BW)])
    assert any(i["key"] == "ion_balance" for i in r["chemistry"]["items"])


def test_balanced_demo_analysis_not_flagged():
    chem = {"calcium_mg_l": 60, "magnesium_mg_l": 25, "hardness_mg_l_caco3": 253, "sodium_mg_l": 750, "chloride_mg_l": 1100,
            "sulfate_mg_l": 300, "alkalinity_mg_l_caco3": 120}
    keys = {i["key"] for i in assess(bw_input(chemistry=chem), [])["chemistry"]["items"]}
    assert not keys & {"ion_balance", "ion_sum", "hardness_check"}


def test_calcium_exceeding_hardness_flagged():
    r = assess(bw_input(chemistry={"calcium_mg_l": 100, "hardness_mg_l_caco3": 50, "magnesium_mg_l": None}), [])
    assert any(i["key"] == "hardness_check" for i in r["chemistry"]["items"])


def test_boron_target_without_measurement_is_explicit():
    r = assess(bw_input(target_boron_mg_l=0.5), [])
    assert next(i for i in r["chemistry"]["items"] if i["key"] == "boron")["status"] == "missing"


def test_demo_origin_is_flagged_in_result():
    r = assess(bw_input(input_origin="demo"), [make_membrane(**FULL_BW)])
    assert r["input_origin"] == "demo"
    assert r["warnings"][0]["title"] == "Demonstration data"
    assert assess(bw_input(), [])["input_origin"] == "client"


# --- Priority 4: client view stays free of internals --------------------------------------------

def test_client_view_strips_new_technical_fields():
    cv = client_view(assess(bw_input(permeate_flow_m3d=5, recovery_pct=50), [make_membrane(**FULL_BW)]))
    c = cv["candidates"][0]
    assert "technical" not in c
    assert all("detail" not in x and "critical" not in x for x in c["checks"])
    assert all("detail" not in i for i in cv["chemistry"]["items"])


def test_ranking_counts_open_issues_before_unknowns():
    # A: one unknown (turbidity limit not documented); B: two cautions (non-comparable test salinity -> permeate + conditions)
    a = make_membrane(1, **FULL_BW)
    b = make_membrane(2, **{**FULL_BW, "max_feed_turbidity_ntu": 1.0, "test_nacl_mg_l": 500})
    r = assess(bw_input(chemistry={"turbidity_ntu": 0.2}), [b, a])
    ca, cb = cand(r, 1), cand(r, 2)
    assert ca["status"] == cb["status"] == "conditional"
    n_open = lambda c: sum(x["status"] in ("warn", "unknown") for x in c["checks"])  # noqa: E731
    assert n_open(ca) < n_open(cb)
    assert r["candidates"][0]["membrane_id"] == 1
