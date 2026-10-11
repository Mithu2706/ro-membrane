"""Recommendation-engine behaviour tests (deterministic rules)."""
import pytest
from pydantic import ValidationError

from app.engine.evidence import MembraneEvidence, ParamValue, resolve_parameters
from app.engine.inputs import AssessmentInput
from app.engine.recommend import assess, client_view

from .conftest import BWRO, SWRO

V, MR = "verified", "manufacturer-rated"


def make_membrane(mid=1, category="BWRO", apps=("bwro",), **params) -> MembraneEvidence:
    rows = [ParamValue(parameter=k, value=v, unit="", evidence_type=MR, verification_status=V, source_id=1)
            for k, v in params.items()]
    chosen, conflicts = resolve_parameters(rows)
    return MembraneEvidence(id=mid, manufacturer="TestCo", model=f"T-{mid}", category=category,
                            intended_applications=list(apps), params=chosen, conflicts=conflicts)


FULL_BW = dict(active_area_m2=37, rated_permeate_flow_m3d=40, rated_salt_rejection_pct=99.5, min_salt_rejection_pct=99.0,
               test_nacl_mg_l=2000, test_pressure_bar=15.5, test_temperature_c=25, test_recovery_pct=15,
               max_operating_pressure_bar=41, max_operating_temperature_c=45, ph_continuous_min=2, ph_continuous_max=11,
               max_free_chlorine_mg_l=0.1, max_feed_sdi=5,
               # synthetic test element: per-element limits documented so a full screening is possible
               max_feed_flow_m3h=19, min_concentrate_permeate_ratio=5)


def bw_input(**over):
    d = {**BWRO, **over}
    d["chemistry"] = {**BWRO["chemistry"], "calcium_mg_l": 10, "alkalinity_mg_l_caco3": 20, "sulfate_mg_l": 20,
                      **over.get("chemistry", {})}
    return AssessmentInput(**d)


def cand(result, mid):
    return next(c for c in result["candidates"] if c["membrane_id"] == mid)


def test_fully_documented_membrane_can_be_suitable():
    r = assess(bw_input(), [make_membrane(**FULL_BW)])
    c = cand(r, 1)
    assert c["status"] == "suitable", [(x["key"], x["status"], x["message"]) for x in c["checks"]]
    assert r["outcome"] == "recommended"
    assert c["estimates"]["required_pressure_bar"] is not None
    assert c["estimates"]["elements_required"] >= 1


def test_unknown_max_pressure_is_never_suitable():
    params = {k: v for k, v in FULL_BW.items() if k != "max_operating_pressure_bar"}
    r = assess(bw_input(), [make_membrane(**params)])
    c = cand(r, 1)
    assert c["status"] == "insufficient_evidence"
    chk = next(x for x in c["checks"] if x["key"] == "pressure_rating")
    assert chk["status"] == "unknown"
    assert r["outcome"] == "no_supported_recommendation"


def test_missing_specifications_remain_missing():
    m = make_membrane(max_operating_pressure_bar=41)
    r = assess(bw_input(), [m])
    c = cand(r, 1)
    assert c["status"] == "insufficient_evidence"
    assert c["rated"]["rated_salt_rejection_pct"] is None
    assert c["estimates"]["permeate_tds_mg_l"] is None
    assert c["estimates"]["required_pressure_bar"] is None


def test_application_mismatch_is_hard_failure():
    r = assess(AssessmentInput(**SWRO), [make_membrane(**FULL_BW)])
    c = cand(r, 1)
    assert c["status"] == "unsuitable"
    assert next(x for x in c["checks"] if x["key"] == "application")["status"] == "fail"
    assert r["outcome"] == "no_supported_recommendation"


def test_seawater_element_for_brackish_is_conditional_not_suitable():
    m = make_membrane(category="SWRO", apps=("swro",), **{**FULL_BW, "max_operating_pressure_bar": 83})
    r = assess(bw_input(available_pressure_bar=40), [m])
    assert cand(r, 1)["status"] in ("conditional", "unsuitable")
    assert cand(r, 1)["status"] != "suitable"


def test_temperature_above_limit_fails():
    r = assess(bw_input(feed_temperature_c=50), [make_membrane(**FULL_BW)])
    c = cand(r, 1)
    assert c["status"] == "unsuitable"
    assert next(x for x in c["checks"] if x["key"] == "temperature")["status"] == "fail"


def test_ph_out_of_range_fails():
    r = assess(bw_input(chemistry={"ph": 11.8}), [make_membrane(**FULL_BW)])
    assert cand(r, 1)["status"] == "unsuitable"


def test_free_chlorine_fails():
    r = assess(bw_input(chemistry={"oxidant_exposure": "free_chlorine_present", "free_chlorine_mg_l": 0.5}),
               [make_membrane(**FULL_BW)])
    assert cand(r, 1)["status"] == "unsuitable"


def test_insufficient_pressure_fails():
    r = assess(bw_input(available_pressure_bar=6), [make_membrane(**FULL_BW)])
    assert cand(r, 1)["status"] == "unsuitable"


def test_osmotic_floor_blocks_any_recommendation():
    inp = AssessmentInput(**{**SWRO, "available_pressure_bar": 40, "recovery_pct": 60})
    m = make_membrane(category="SWRO", apps=("swro",), **{**FULL_BW, "max_operating_pressure_bar": 83})
    r = assess(inp, [m])
    assert r["outcome"] == "no_supported_recommendation"
    assert any(c["key"] == "osmotic_floor" and c["status"] == "fail" for c in r["system"]["checks"])


def test_feed_flow_limit():
    r = assess(bw_input(feed_flow_limit_m3d=1000), [make_membrane(**FULL_BW)])
    assert r["outcome"] == "no_supported_recommendation"
    assert any(c["key"] == "feed_flow_limit" and c["status"] == "fail" for c in r["system"]["checks"])


def test_insufficient_chemistry_for_industrial():
    inp = AssessmentInput(application="industrial", feed_tds_mg_l=3000, feed_temperature_c=25, available_pressure_bar=20,
                          permeate_flow_m3d=500, recovery_pct=70, design_flux_lmh=18)
    m = make_membrane(category="BWRO-fouling-resistant", apps=("bwro",), **FULL_BW)
    r = assess(inp, [m])
    c = cand(r, 1)
    assert c["status"] == "insufficient_evidence"
    assert r["chemistry"]["completeness"] == "insufficient"
    assert r["outcome"] == "no_supported_recommendation"


def test_missing_chemistry_caps_bwro_at_conditional():
    inp = AssessmentInput(**{**BWRO, "chemistry": {}})
    r = assess(inp, [make_membrane(**FULL_BW)])
    assert cand(r, 1)["status"] == "conditional"


def test_zero_is_distinct_from_missing():
    with_zero = AssessmentInput(**{**BWRO, "chemistry": {**BWRO["chemistry"], "silica_mg_l": 0}})
    missing = AssessmentInput(**{**BWRO, "chemistry": {k: v for k, v in BWRO["chemistry"].items() if k != "silica_mg_l"}})
    assert with_zero.chemistry.silica_mg_l == 0
    assert missing.chemistry.silica_mg_l is None
    silica = lambda res: next(i for i in res["chemistry"]["items"] if i["key"] == "silica")["status"]  # noqa: E731
    assert silica(assess(with_zero, [make_membrane(**FULL_BW)])) == "ok"
    assert silica(assess(missing, [make_membrane(**FULL_BW)])) == "missing"  # explicit uncertainty, not silence


@pytest.mark.parametrize("rec", [0, 100, -5, 120])
def test_invalid_recovery_input(rec):
    with pytest.raises(ValidationError):
        AssessmentInput(**{**BWRO, "recovery_pct": rec})


def test_priority_never_overrides_status_tier():
    good = make_membrane(1, **FULL_BW)
    # Better rejection but no documented pressure rating -> insufficient evidence
    risky = make_membrane(2, **{k: v for k, v in {**FULL_BW, "rated_salt_rejection_pct": 99.9}.items()
                                 if k != "max_operating_pressure_bar"})
    r = assess(bw_input(priority="quality"), [risky, good])
    assert r["candidates"][0]["membrane_id"] == 1
    assert r["recommended"]["membrane_id"] == 1


def test_priority_orders_within_tier():
    a = make_membrane(1, **FULL_BW)
    b = make_membrane(2, **{**FULL_BW, "rated_permeate_flow_m3d": 48})  # more permeable
    r = assess(bw_input(priority="low_pressure"), [a, b])
    assert r["candidates"][0]["membrane_id"] == 2


def test_conflicting_sources_are_flagged():
    rows = [ParamValue("rated_salt_rejection_pct", 99.7, "%", MR, V, 1),
            ParamValue("rated_salt_rejection_pct", 99.82, "%", MR, "report-extracted", 2)]
    chosen, conflicts = resolve_parameters(rows)
    assert chosen["rated_salt_rejection_pct"].value == 99.7  # verified wins
    assert "rated_salt_rejection_pct" in conflicts


def test_experimental_observations_never_used_as_ratings():
    rows = [ParamValue("rated_salt_rejection_pct", 98.8, "%", "pilot-plant", V, 1)]
    chosen, _ = resolve_parameters(rows)
    assert "rated_salt_rejection_pct" not in chosen


def test_client_view_hides_internal_details():
    r = assess(bw_input(), [make_membrane(**FULL_BW)])
    cv = client_view(r)
    assert "technical" not in cv
    assert "technical" not in cv["recommended"]
    assert all("detail" not in c for c in cv["recommended"]["checks"])
    assert "technical" in r  # the full record keeps them for admin/report


def test_seed_dataset_swro_and_bwro(membranes):
    r = assess(AssessmentInput(**SWRO), membranes)
    assert r["outcome"] == "recommended"
    assert r["recommended"]["category"].startswith("SWRO")
    # Membranes without documented limits are never recommended
    for c in r["candidates"]:
        if c["rated"]["max_operating_pressure_bar"] is None:
            assert c["status"] in ("insufficient_evidence", "unsuitable")
    r2 = assess(AssessmentInput(**BWRO), membranes)
    assert r2["recommended"]["category"].startswith("BWRO")
