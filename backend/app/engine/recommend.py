"""Deterministic recommendation engine.

Sequence (mirrors the screening algorithm in the supplied review, §6):
 1. Validate inputs (pydantic) and compute the system flow balance.
 2. System-level feasibility: feed-flow limit, osmotic pressure floor, input range.
 3. Chemistry screening (scaling, fouling, oxidants, boron, completeness).
 4. Per membrane: application compatibility, documented operating limits,
    rated-performance availability, test-condition comparability, indicative
    pressure and permeate estimates, chemistry-driven conditions.
 5. Status per candidate:
      any hard failure                          -> unsuitable
      else any unknown *critical* evidence      -> insufficient_evidence
      else any caution / non-critical unknown   -> conditional
      else                                      -> suitable (for preliminary evaluation)
    A candidate is never "suitable" when a relevant limit is simply not recorded.
 6. Ranking is lexicographic, not a weighted score:
      (status tier, number of open issues (cautions + unknowns), number of unknowns,
       client-priority metric, fewer verified critical parameters,
       distance between rated test salinity and the client's feed, name)
 7. The top candidate is recommended only if its tier is suitable or conditional
    and no system-level hard failure exists; otherwise the result is
    "no supported recommendation".
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

from . import ENGINE_VERSION
from .chemistry import SDI_GENERAL_LIMIT, ChemistryResult, screen
from .evidence import MembraneEvidence, is_ambiguous_conflict
from .hydraulics import (
    average_feed_side_concentration,
    concentrate_concentration_mass_balance,
    concentration_factor_ideal,
    flow_balance,
    osmotic_pressure_bar,
    permeance_from_rating,
    permeate_concentration,
    required_feed_pressure_bar,
)
from .inputs import APPLICATION_LABELS, PRIORITY_LABELS, AssessmentInput
from .units import flow_m3d_from_flux, flux_lmh_from_flow, m3d_to_m3h

# POLICY constants (documented engine choices, not literature values) ----------
PRESSURE_MARGIN_FRACTION = 0.10  # estimated requirement within 10% of available pressure -> marginal
ELEMENT_FLOW_TOLERANCE = 0.85  # datasheets state individual elements may deliver up to 15% below rated flow
COMPARABLE_SALINITY_RATIO = 3.0  # rated test salinity within ×/÷3 of the client's average feed-side salinity
COMPARABLE_TEMPERATURE_DELTA_C = 5.0
CALC_RANGE_TDS_MG_L = (100.0, 70000.0)
CALC_RANGE_TEMPERATURE_C = (5.0, 45.0)
ASSUMED_TEST_TEMPERATURE_C = 25.0  # used only for the osmotic term when a source omits test temperature
OVERSIZE_FLUX_FRACTION = 2.0 / 3.0  # implied operating flux below 2/3 of design flux -> element oversized for the duty

# Parameters whose disagreement between equally-verified sources blocks a confident assessment
SAFETY_PARAMETERS = {
    "max_operating_pressure_bar", "max_operating_temperature_c", "ph_continuous_min", "ph_continuous_max",
    "max_free_chlorine_mg_l", "max_feed_sdi", "max_feed_turbidity_ntu", "min_concentrate_permeate_ratio",
    "rated_permeate_flow_m3d", "rated_flux_lmh", "active_area_m2", "rated_salt_rejection_pct", "min_salt_rejection_pct",
    "test_nacl_mg_l", "test_pressure_bar",
}
# Chemistry items handled by dedicated per-membrane checks rather than the aggregate chemistry check
_PER_MEMBRANE_CHEM_KEYS = {"oxidant", "sdi", "boron"}

STATUS_ORDER = {"suitable": 0, "conditional": 1, "insufficient_evidence": 2, "unsuitable": 3}
STATUS_LABELS = {
    "suitable": "Suitable for preliminary evaluation",
    "conditional": "Conditional",
    "insufficient_evidence": "Insufficient evidence",
    "unsuitable": "Unsuitable",
}

# Application × membrane category compatibility.
# compatible  -> pass; conditional -> caution; anything missing -> incompatible (hard failure)
COMPATIBILITY: dict[str, dict[str, str]] = {
    "swro": {"SWRO": "compatible", "SWRO-low-energy": "compatible"},
    "bwro": {"BWRO": "compatible", "BWRO-low-energy": "compatible", "BWRO-fouling-resistant": "compatible",
             "BWRO-high-rejection": "compatible", "SWRO": "conditional", "SWRO-low-energy": "conditional",
             "Industrial": "conditional"},
    "industrial": {"Industrial": "compatible", "BWRO-fouling-resistant": "compatible", "BWRO": "conditional",
                   "BWRO-low-energy": "conditional", "BWRO-high-rejection": "conditional", "SWRO": "conditional",
                   "SWRO-low-energy": "conditional"},
    "second_pass": {"BWRO-high-rejection": "compatible", "BWRO-low-energy": "compatible", "BWRO": "compatible",
                    "BWRO-fouling-resistant": "conditional", "SWRO-low-energy": "conditional", "SWRO": "conditional",
                    "Industrial": "conditional"},
    "other": {c: "conditional" for c in ("BWRO", "BWRO-low-energy", "BWRO-fouling-resistant", "BWRO-high-rejection",
                                         "SWRO", "SWRO-low-energy", "Industrial")},
}

CATEGORY_LABELS = {
    "BWRO": "Brackish water",
    "BWRO-low-energy": "Brackish water, low energy",
    "BWRO-fouling-resistant": "Brackish water, fouling resistant",
    "BWRO-high-rejection": "Brackish water, high rejection",
    "SWRO": "Seawater",
    "SWRO-low-energy": "Seawater, low energy",
    "Industrial": "Industrial / wastewater",
}


@dataclass
class Check:
    key: str
    label: str
    status: str  # pass | warn | fail | unknown
    message: str
    detail: str = ""
    critical: bool = False

    def as_dict(self) -> dict:
        return dict(self.__dict__)


@dataclass
class SystemContext:
    inp: AssessmentInput
    flow: object
    cf: float
    cc_ideal: float
    c_avg: float
    pi_feed: float
    pi_avg: float
    pi_conc: float
    loss: float
    chem: ChemistryResult
    checks: list[Check] = field(default_factory=list)

    @property
    def hard_fail(self) -> bool:
        return any(c.status == "fail" for c in self.checks)


def _fmt(v: float | None, nd: int = 1) -> str:
    return "—" if v is None else f"{v:,.{nd}f}"


def _param_view(m: MembraneEvidence, key: str) -> dict | None:
    p = m.get(key)
    if p is None:
        return None
    return {"value": p.value, "value_min": p.value_min, "value_max": p.value_max, "value_text": p.value_text,
            "unit": p.unit, "evidence_type": p.evidence_type, "verification_status": p.verification_status,
            "source_id": p.source_id, "test_conditions": p.test_conditions}


RATED_KEYS = [
    ("active_area_m2", "Active membrane area"),
    ("rated_permeate_flow_m3d", "Rated permeate flow"),
    ("rated_flux_lmh", "Rated flux"),
    ("rated_salt_rejection_pct", "Rated salt rejection"),
    ("min_salt_rejection_pct", "Minimum salt rejection"),
    ("boron_rejection_pct", "Boron rejection"),
    ("max_operating_pressure_bar", "Maximum operating pressure"),
    ("max_operating_temperature_c", "Maximum operating temperature"),
    ("ph_continuous_min", "pH, continuous (min)"),
    ("ph_continuous_max", "pH, continuous (max)"),
    ("max_free_chlorine_mg_l", "Free chlorine tolerance"),
    ("max_feed_sdi", "Maximum feed SDI"),
    ("max_feed_turbidity_ntu", "Maximum feed turbidity"),
    ("max_element_pressure_drop_bar", "Maximum element pressure drop"),
    ("max_feed_flow_m3h", "Maximum feed flow per element"),
    ("test_nacl_mg_l", "Test salinity (NaCl)"),
    ("test_pressure_bar", "Test pressure"),
    ("test_temperature_c", "Test temperature"),
    ("test_recovery_pct", "Test recovery"),
]


def build_system(inp: AssessmentInput) -> SystemContext:
    fb = flow_balance(inp.permeate_flow_m3d, inp.recovery)
    cf = concentration_factor_ideal(inp.recovery)
    cc = inp.feed_tds_mg_l * cf
    c_avg = average_feed_side_concentration(inp.feed_tds_mg_l, inp.recovery)
    t = inp.feed_temperature_c
    ctx = SystemContext(
        inp=inp, flow=fb, cf=cf, cc_ideal=cc, c_avg=c_avg,
        pi_feed=osmotic_pressure_bar(inp.feed_tds_mg_l, t), pi_avg=osmotic_pressure_bar(c_avg, t),
        pi_conc=osmotic_pressure_bar(cc, t), loss=inp.pressure_loss_allowance_bar or 0.0, chem=screen(inp),
    )

    # Feed-flow availability
    if inp.feed_flow_limit_m3d is not None:
        if fb.feed_m3d > inp.feed_flow_limit_m3d:
            ctx.checks.append(Check("feed_flow_limit", "Feed water availability", "fail",
                                    f"The target production at {inp.recovery_pct:g}% recovery needs about "
                                    f"{fb.feed_m3d:,.0f} m³/day of feed, more than the {inp.feed_flow_limit_m3d:,.0f} m³/day available. "
                                    "Increase recovery (if chemistry allows) or reduce the production target.",
                                    f"Qf = Qp/r = {fb.feed_m3d:.1f} m³/d > limit {inp.feed_flow_limit_m3d:.1f} m³/d", True))
        else:
            ctx.checks.append(Check("feed_flow_limit", "Feed water availability", "pass",
                                    "Enough feed water is available for the target production.",
                                    f"Qf = {fb.feed_m3d:.1f} ≤ {inp.feed_flow_limit_m3d:.1f} m³/d"))

    # Osmotic floor
    floor = ctx.pi_conc + ctx.loss
    if floor >= inp.available_pressure_bar:
        ctx.checks.append(Check("osmotic_floor", "Pressure vs. salinity", "fail",
                                "The available pressure is not enough to overcome the osmotic pressure of the concentrate "
                                f"at {inp.recovery_pct:g}% recovery. Lower the recovery target or increase available pressure.",
                                f"π_conc,ideal = {ctx.pi_conc:.1f} bar (+ losses {ctx.loss:.1f}) ≥ P_avail {inp.available_pressure_bar:.1f} bar",
                                True))
    else:
        ctx.checks.append(Check("osmotic_floor", "Pressure vs. salinity", "pass",
                                "Available pressure exceeds the estimated osmotic pressure of the concentrate.",
                                f"π_conc,ideal = {ctx.pi_conc:.1f} bar < P_avail {inp.available_pressure_bar:.1f} bar"))

    # Calculation range
    lo, hi = CALC_RANGE_TDS_MG_L
    tlo, thi = CALC_RANGE_TEMPERATURE_C
    out = []
    if not lo <= inp.feed_tds_mg_l <= hi:
        out.append(f"feed TDS {inp.feed_tds_mg_l:,.0f} mg/L")
    if not tlo <= inp.feed_temperature_c <= thi:
        out.append(f"temperature {inp.feed_temperature_c:g} °C")
    if out:
        ctx.checks.append(Check("calc_range", "Calculation range", "warn",
                                "Some inputs are outside the range in which this preliminary screening is meaningful ("
                                + ", ".join(out) + "). Treat results with extra caution.",
                                f"POLICY range TDS {lo:.0f}-{hi:.0f} mg/L, T {tlo:.0f}-{thi:.0f} °C"))
    return ctx


def _rated_flux(m: MembraneEvidence) -> tuple[float | None, str]:
    flux = m.num("rated_flux_lmh")
    if flux is not None:
        return flux, "rated flux as reported"
    flow, area = m.num("rated_permeate_flow_m3d"), m.num("active_area_m2")
    if flow is not None and area:
        return flux_lmh_from_flow(flow, area), f"rated flow {flow} m³/d ÷ area {area} m²"
    return None, ""


def _arrangement_check(m: MembraneEvidence, ctx: SystemContext, elements: int, test_r: float | None,
                       checks: list, tech: dict) -> None:
    """Membrane-level check of documented per-element feed-flow and recovery limits.

    This is not a plant design. It asks two questions about N elements of this model:
      1. Rigorous bound: even with every element fed in parallel, each lead element receives at least Qf/N.
         If that exceeds the documented maximum feed flow, no arrangement of N elements can comply (hard failure).
      2. Existence: is there an idealised uniform array (n_p parallel lines of n_s elements in series, equal
         recovery per element) meeting every DOCUMENTED limit? Real designs are staged, so "none" is a caution,
         not a failure. Undocumented limits (minimum concentrate flow, vessel length, etc.) are reported as unknown.
    """
    r = ctx.inp.recovery
    qf_m3h = ctx.flow.feed_m3d / 24.0
    fmax = m.num("max_feed_flow_m3h")
    ratio = m.num("min_concentrate_permeate_ratio")
    rmax = 1.0 / (1.0 + ratio) if ratio is not None else None
    lead_parallel = qf_m3h / elements
    rec_series = 1.0 - (1.0 - r) ** (1.0 / elements)
    tech.update(lead_feed_all_parallel_m3h=lead_parallel, per_element_recovery_all_series=rec_series,
                max_feed_flow_m3h=fmax, max_element_recovery=rmax)
    if fmax is not None and lead_parallel > fmax:
        checks.append(Check("arrangement", "Element feed flow and recovery limits", "fail",
                            f"Even with every element fed in parallel, each would receive about {lead_parallel:,.1f} m³/h of "
                            f"feed, above the documented maximum of {fmax:g} m³/h for this element. A lower design flux (more "
                            "elements) would be needed.",
                            f"Qf/N = {lead_parallel:.2f} m3/h > Fmax {fmax:g} m3/h (bound valid for any arrangement)", True))
        return
    found = None
    for n_s in range(1, elements + 1):
        n_p = elements // n_s
        lead = qf_m3h / n_p
        rec_el = 1.0 - (1.0 - r) ** (1.0 / n_s)
        if (fmax is None or lead <= fmax) and (rmax is None or rec_el <= rmax):
            found = (n_s, n_p, lead, rec_el)
            break
    undocumented = []
    if fmax is None:
        undocumented.append("maximum feed flow per element")
    if ratio is None:
        undocumented.append("minimum concentrate flow (or concentrate-to-permeate ratio) per element")
    if found is None:
        checks.append(Check("arrangement", "Element feed flow and recovery limits", "warn",
                            f"No simple arrangement of about {elements} element(s) keeps every element within its documented "
                            f"feed-flow and recovery limits at {ctx.inp.recovery_pct:g}% recovery. A staged design, concentrate "
                            "recirculation or more elements would be needed.",
                            f"No uniform n_s x n_p array satisfies Fmax={fmax}, r_el,max={rmax}; all-series r_el={rec_series:.3f}"))
        return
    n_s, n_p, lead, rec_el = found
    tech.update(example_array_series=n_s, example_array_parallel=n_p)
    detail = (f"Example uniform array: {n_p} parallel line(s) x {n_s} element(s) in series; lead feed {lead:.2f} m3/h; "
              f"recovery per element {rec_el:.3f}")
    if test_r is not None and ratio is None:
        detail += f"; rated test recovery {test_r / 100:.3f} (not a limit)"
    if undocumented:
        checks.append(Check("arrangement", "Element feed flow and recovery limits", "unknown",
                            "Element flow limits could only be partly checked. Not documented for this element: "
                            + "; ".join(undocumented) + ". Vessel layout and staging have not been designed.",
                            detail))
    else:
        checks.append(Check("arrangement", "Element feed flow and recovery limits", "pass",
                            "At membrane level, the element count can be arranged within the documented per-element feed-flow "
                            "and recovery limits. Vessel layout and staging have not been designed.", detail))


def evaluate(m: MembraneEvidence, ctx: SystemContext) -> dict:
    inp, ch = ctx.inp, ctx.inp.chemistry
    checks: list[Check] = []
    concerns: list[str] = []
    positives: list[str] = []
    tech: dict = {}

    # 1. Application compatibility -------------------------------------------
    compat = COMPATIBILITY.get(inp.application, {}).get(m.category, "incompatible")
    if compat == "conditional" and inp.application in m.intended_applications and inp.application != "other":
        compat = "compatible"  # source explicitly documents this service
    app_label = APPLICATION_LABELS[inp.application]
    cat_label = CATEGORY_LABELS.get(m.category, m.category)
    if compat == "compatible":
        checks.append(Check("application", "Application fit", "pass",
                            f"{cat_label} element documented for {app_label} service.",
                            f"category={m.category}, intended={m.intended_applications}"))
        positives.append(f"Designed for {app_label} service")
    elif compat == "conditional":
        checks.append(Check("application", "Application fit", "warn",
                            f"This {cat_label.lower()} element is not the usual choice for {app_label}; it may "
                            "be used only after specific engineering review.",
                            f"category={m.category} conditional for {inp.application}"))
    else:
        checks.append(Check("application", "Application fit", "fail",
                            f"This {cat_label.lower()} element is not intended for {app_label} service.",
                            f"category={m.category} incompatible with {inp.application}", True))

    # 2. Rated performance and apparent permeance ------------------------------
    flux, flux_basis = _rated_flux(m)
    test_c, test_p = m.num("test_nacl_mg_l"), m.num("test_pressure_bar")
    test_t, test_r = m.num("test_temperature_c"), m.num("test_recovery_pct")
    rej = m.num_low("rated_salt_rejection_pct")
    min_rej = m.num_low("min_salt_rejection_pct")
    if rej is None:
        rej = min_rej
    A = None
    perf_notes = []
    if flux is not None and test_c is not None and test_p is not None:
        t_pi = test_t if test_t is not None else ASSUMED_TEST_TEMPERATURE_C
        if test_t is None:
            perf_notes.append("test temperature not reported")
        if test_r is not None:
            c_test = average_feed_side_concentration(test_c, test_r / 100.0)
        else:
            c_test = test_c
            perf_notes.append("test recovery not reported")
        pi_test = osmotic_pressure_bar(c_test, t_pi)
        A = permeance_from_rating(flux, test_p, pi_test)
        tech.update(rated_flux_lmh=flux, flux_basis=flux_basis, test_avg_conc_mg_l=c_test, test_osmotic_avg_bar=pi_test,
                    test_ndp_bar=test_p - pi_test, apparent_permeance_lmh_bar=A,
                    test_temperature_assumed=test_t is None)
    missing_perf = [n for n, v in (("rated flow/flux", flux), ("test salinity", test_c), ("test pressure", test_p)) if v is None]
    if A is None:
        checks.append(Check("performance_data", "Rated performance data", "unknown",
                            "The manufacturer's rated output and test conditions are not documented in the dataset, so "
                            "pressure and output cannot be estimated for this membrane.",
                            "Missing: " + (", ".join(missing_perf) or "positive net driving pressure at test point"), True))
    elif perf_notes:
        checks.append(Check("performance_data", "Rated performance data", "warn",
                            "Rated performance is documented but some test conditions are missing, so estimates are less certain.",
                            "; ".join(perf_notes) + f"; A = {A:.3f} LMH/bar"))
    else:
        checks.append(Check("performance_data", "Rated performance data", "pass",
                            "Rated output and full test conditions are documented.", f"A = {A:.3f} LMH/bar ({flux_basis})"))

    # 2b. Source agreement ---------------------------------------------------------
    ambiguous = sorted(p for p, c in m.conflicts.items() if p in SAFETY_PARAMETERS and is_ambiguous_conflict(c))
    resolved = sorted(p for p in m.conflicts if p not in ambiguous)
    if ambiguous:
        checks.append(Check("source_conflict", "Source agreement", "unknown",
                            "Equally reliable sources report different values for key specifications, so the applicable "
                            "value cannot be determined until the records are reviewed.",
                            "Ambiguous conflicts: " + ", ".join(ambiguous), True))
    elif resolved:
        checks.append(Check("source_conflict", "Source agreement", "warn",
                            "Sources disagree on some specifications; the best-verified value is used.",
                            "Resolved conflicts: " + ", ".join(resolved)))

    # 3. Element sizing and operating flux ---------------------------------------
    # The element count is rounded up, so the system actually operates at an average flux at or
    # below the design flux. Pressure is estimated at that implied flux so that pressure, flux and
    # element count describe the same system.
    area = m.num("active_area_m2")
    elements = per_element = implied_flux = None
    if area and inp.design_flux_lmh:
        per_element = flow_m3d_from_flux(inp.design_flux_lmh, area)
        elements = math.ceil(inp.permeate_flow_m3d / per_element)
        implied_flux = flux_lmh_from_flow(inp.permeate_flow_m3d, elements * area)
        tech.update(permeate_per_element_m3d=per_element, elements_required=elements, implied_flux_lmh=implied_flux)
        if implied_flux < inp.design_flux_lmh * OVERSIZE_FLUX_FRACTION:
            checks.append(Check("element_sizing", "Element size vs. production", "warn",
                                f"One element of this size would produce about {per_element:,.1f} m³/day at the design flux, "
                                f"well above the {inp.permeate_flow_m3d:,.1f} m³/day requested. It would run at a much lower "
                                "flux than intended; a smaller element format may suit this duty better.",
                                f"N = {elements}; implied flux {implied_flux:.1f} LMH vs design {inp.design_flux_lmh:g} LMH"))
        _arrangement_check(m, ctx, elements, test_r, checks, tech)
    else:
        checks.append(Check("arrangement", "Element feed flow and recovery limits", "unknown",
                            "Per-element feed-flow and recovery limits were not checked because the element count could not "
                            "be estimated (design flux or active membrane area missing).", "N not estimated"))
    op_flux = implied_flux if implied_flux is not None else inp.design_flux_lmh

    # 4. Pressure requirement ---------------------------------------------------
    p_req = p_req_high = None
    floor = ctx.pi_conc + ctx.loss
    if A is not None and op_flux is not None:
        p_req = required_feed_pressure_bar(op_flux, A, ctx.pi_avg, ctx.pi_conc, ctx.loss)
        p_req_high = required_feed_pressure_bar(op_flux, A * ELEMENT_FLOW_TOLERANCE, ctx.pi_avg, ctx.pi_conc, ctx.loss)
        tech.update(required_pressure_bar=p_req, required_pressure_high_bar=p_req_high, pressure_basis_flux_lmh=op_flux)
        pav = inp.available_pressure_bar
        if p_req > pav:
            checks.append(Check("pressure_available", "Pressure requirement", "fail",
                                f"Estimated feed pressure (about {p_req:.0f} bar) exceeds the {pav:g} bar available at the "
                                "chosen design flux.",
                                f"P_req = max(J/A + π_avg, π_conc) + losses = {p_req:.1f} bar at J = {op_flux:.1f} LMH", True))
        elif p_req_high > pav or (pav - p_req) / pav < PRESSURE_MARGIN_FRACTION:
            checks.append(Check("pressure_available", "Pressure requirement", "warn",
                                f"Estimated pressure ({p_req:.0f}–{p_req_high:.0f} bar) is close to the {pav:g} bar available; "
                                "there is little margin for fouling, cold water or pressure losses.",
                                f"P_req {p_req:.1f}-{p_req_high:.1f} bar vs available {pav:.1f} bar"))
        else:
            checks.append(Check("pressure_available", "Pressure requirement", "pass",
                                f"Estimated pressure ({p_req:.0f}–{p_req_high:.0f} bar) is within the {pav:g} bar available.",
                                f"P_req {p_req:.1f}-{p_req_high:.1f} bar"))
            positives.append("Fits within your available pressure")
        if inp.pressure_loss_allowance_bar is None:
            concerns.append("Pressure losses through vessels and piping are not included in the pressure estimate.")
    elif A is not None:
        checks.append(Check("pressure_available", "Pressure requirement", "warn",
                            "A design flux was not provided, so the operating pressure was not estimated; only the "
                            "salinity-driven minimum was checked.", f"Osmotic floor {floor:.1f} bar"))
    else:
        checks.append(Check("pressure_available", "Pressure requirement", "unknown",
                            "Operating pressure could not be estimated because rated performance data are missing.",
                            "No apparent permeance available"))

    # 5. Pressure rating ----------------------------------------------------------
    pmax = m.num("max_operating_pressure_bar")
    if pmax is None:
        checks.append(Check("pressure_rating", "Pressure rating", "unknown",
                            "The maximum operating pressure is not documented. The membrane cannot be confirmed as safe "
                            "for the pressures involved.", "max_operating_pressure_bar not reported", True))
    else:
        need = p_req if p_req is not None else floor
        if need > pmax:
            checks.append(Check("pressure_rating", "Pressure rating", "fail",
                                f"The pressure needed (at least {need:.0f} bar) exceeds this element's documented maximum of "
                                f"{pmax:g} bar.", f"need {need:.1f} > pmax {pmax:.1f} bar", True))
        elif p_req_high is not None and p_req_high > pmax:
            checks.append(Check("pressure_rating", "Pressure rating", "warn",
                                f"The upper pressure estimate approaches the documented maximum of {pmax:g} bar.",
                                f"P_req,high {p_req_high:.1f} > pmax {pmax:.1f}"))
        else:
            checks.append(Check("pressure_rating", "Pressure rating", "pass",
                                f"Estimated pressures are below the documented maximum of {pmax:g} bar.",
                                f"need {need:.1f} ≤ pmax {pmax:.1f} bar"))
        if inp.available_pressure_bar > pmax:
            concerns.append(f"Your pump can exceed this element's {pmax:g} bar rating; feed pressure must be limited.")

    # 5. Temperature ---------------------------------------------------------------
    tmax = m.num("max_operating_temperature_c")
    if tmax is None:
        checks.append(Check("temperature", "Temperature limit", "unknown",
                            "The maximum operating temperature is not documented.", "max_operating_temperature_c not reported", True))
    elif inp.feed_temperature_c > tmax:
        checks.append(Check("temperature", "Temperature limit", "fail",
                            f"Feed temperature {inp.feed_temperature_c:g} °C exceeds the documented maximum of {tmax:g} °C.",
                            f"T {inp.feed_temperature_c} > {tmax}", True))
    else:
        checks.append(Check("temperature", "Temperature limit", "pass",
                            f"Feed temperature is within the documented limit ({tmax:g} °C).", ""))
        if ch.ph is not None and ch.ph > 10 and inp.feed_temperature_c > 35:
            concerns.append("Datasheets restrict continuous operation above pH 10 to 35 °C.")

    # 6. pH -------------------------------------------------------------------------
    pmin_ph, pmax_ph = m.num("ph_continuous_min"), m.num("ph_continuous_max")
    if ch.ph is None:
        checks.append(Check("ph", "pH limit", "unknown", "Feed pH was not provided, so pH limits could not be checked.", ""))
    elif pmin_ph is None or pmax_ph is None:
        checks.append(Check("ph", "pH limit", "unknown", "This membrane's continuous pH range is not documented.", ""))
    elif not pmin_ph <= ch.ph <= pmax_ph:
        checks.append(Check("ph", "pH limit", "fail",
                            f"Feed pH {ch.ph:g} is outside the documented continuous range ({pmin_ph:g}–{pmax_ph:g}).",
                            "", True))
    else:
        checks.append(Check("ph", "pH limit", "pass", f"Feed pH is within the documented range ({pmin_ph:g}–{pmax_ph:g}).", ""))

    # 7. Oxidants -------------------------------------------------------------------
    tol = m.num("max_free_chlorine_mg_l")
    fc = ch.free_chlorine_mg_l
    chlorine_present = ch.oxidant_exposure == "free_chlorine_present" or (fc is not None and fc > 0)
    if chlorine_present:
        if fc is not None and tol is not None and fc < tol:
            checks.append(Check("oxidant", "Chlorine tolerance", "warn",
                                "Free chlorine is measurable though below the stated tolerance. Dechlorination is still strongly recommended.",
                                f"free Cl {fc} < tolerance {tol}"))
        else:
            checks.append(Check("oxidant", "Chlorine tolerance", "fail",
                                "Free chlorine in the RO feed will damage this membrane. Chlorine must be removed upstream "
                                "before this membrane can be considered.",
                                f"free Cl {fc}, tolerance {tol}", True))
    elif ch.oxidant_exposure == "unknown":
        checks.append(Check("oxidant", "Chlorine tolerance", "unknown",
                            "Chlorine/oxidant exposure was not specified.", f"tolerance {tol}"))
    elif ch.oxidant_exposure == "chloramine":
        checks.append(Check("oxidant", "Chlorine tolerance", "warn",
                            "Chloramine is present. Its long-term effect on this membrane is not covered by the documented "
                            "free-chlorine tolerance; confirm compatibility with the manufacturer.",
                            f"chloramine; documented free-chlorine tolerance {tol}"))
    elif tol is None:
        checks.append(Check("oxidant", "Chlorine tolerance", "unknown",
                            "This membrane's chlorine tolerance is not documented.", ""))
    else:
        checks.append(Check("oxidant", "Chlorine tolerance", "pass", "No free chlorine reported in the RO feed.", ""))

    # 8. Particulate limits --------------------------------------------------------
    # Every measured value needs a documented limit, and every documented limit needs a measurement.
    sdi_max, turb_max = m.num("max_feed_sdi"), m.num("max_feed_turbidity_ntu")
    foul_fail, foul_unknown = [], []
    for value, limit, name, unit in ((ch.sdi, sdi_max, "SDI", ""), (ch.turbidity_ntu, turb_max, "turbidity", " NTU")):
        if value is not None and limit is not None and value > limit:
            foul_fail.append(f"{name} {value:g}{unit} exceeds the documented maximum of {limit:g}{unit}")
        elif value is not None and limit is None:
            foul_unknown.append(f"{name} limit not documented")
        elif value is None and limit is not None:
            foul_unknown.append(f"feed {name} not provided (limit {limit:g}{unit})")
    if ch.sdi is None and ch.turbidity_ntu is None:
        foul_unknown.append("feed SDI/turbidity not provided")
    # An SDI above every verified datasheet limit cannot be accepted on the basis of a missing limit.
    sdi_critical = ch.sdi is not None and ch.sdi > SDI_GENERAL_LIMIT and sdi_max is None
    if foul_fail:
        checks.append(Check("particulates", "Feed fouling limits", "fail",
                            "Feed quality exceeds this membrane's documented limits (" + "; ".join(foul_fail) +
                            "). Improve pretreatment first.", "", True))
    elif foul_unknown:
        checks.append(Check("particulates", "Feed fouling limits", "unknown",
                            "Feed fouling limits could not be fully checked (" + "; ".join(dict.fromkeys(foul_unknown)) + ").",
                            "SDI above all verified datasheet limits with no documented limit" if sdi_critical else "",
                            sdi_critical))
    else:
        checks.append(Check("particulates", "Feed fouling limits", "pass",
                            "Feed SDI/turbidity are within this membrane's documented limits.", ""))

    # 9. Permeate quality ----------------------------------------------------------
    cp = cp_high = None
    comparable = None
    if rej is not None and test_c is not None:
        ratio = ctx.c_avg / test_c
        comparable = (1.0 / COMPARABLE_SALINITY_RATIO) <= ratio <= COMPARABLE_SALINITY_RATIO
        cp = permeate_concentration(ctx.c_avg, rej)
        cp_high = permeate_concentration(ctx.c_avg, min_rej) if min_rej is not None and min_rej < rej else None
        tech.update(permeate_estimate_mg_l=cp, permeate_estimate_high_mg_l=cp_high, rejection_used_pct=rej,
                    salinity_ratio_client_to_test=ratio)
    target = inp.target_permeate_tds_mg_l
    if target is not None:
        if cp is None:
            checks.append(Check("permeate_quality", "Permeate quality target", "unknown",
                                "Permeate quality could not be estimated because rated rejection or its test salinity is not documented.", ""))
        elif not comparable:
            checks.append(Check("permeate_quality", "Permeate quality target", "warn",
                                "The manufacturer's rejection was measured at a very different salinity, so the permeate "
                                "estimate is low-confidence.", f"Cp≈{cp:.1f} mg/L; salinity ratio {tech['salinity_ratio_client_to_test']:.2f}"))
        elif cp > target:
            checks.append(Check("permeate_quality", "Permeate quality target", "warn",
                                f"Estimated permeate TDS (about {cp:.0f} mg/L) may exceed your {target:g} mg/L target. A "
                                "second pass or a higher-rejection element may be required.", f"Cp≈{cp:.1f} > {target}"))
        elif cp_high is not None and cp_high > target:
            checks.append(Check("permeate_quality", "Permeate quality target", "warn",
                                f"Estimated permeate TDS ({cp:.0f}–{cp_high:.0f} mg/L) spans your {target:g} mg/L target.",
                                f"Cp {cp:.1f}-{cp_high:.1f}"))
        else:
            checks.append(Check("permeate_quality", "Permeate quality target", "pass",
                                f"Estimated permeate TDS is below your {target:g} mg/L target.", f"Cp≈{cp:.1f}"))
            positives.append("Expected to meet your permeate quality target")
    if inp.design_flux_lmh is not None and flux is not None and inp.design_flux_lmh < flux and cp is not None:
        concerns.append("At a design flux below the rated test flux, salt passage is typically higher than the rated value implies.")

    # 10. Test-condition comparability --------------------------------------------
    comp_issues = []
    if comparable is False:
        comp_issues.append("rated test salinity differs strongly from your feed")
    if test_t is not None and abs(inp.feed_temperature_c - test_t) > COMPARABLE_TEMPERATURE_DELTA_C:
        if inp.feed_temperature_c < test_t:
            comp_issues.append("your water is colder than the test condition (more pressure likely needed)")
        else:
            comp_issues.append("your water is warmer than the test condition (salt passage likely higher)")
    if test_c is None:
        checks.append(Check("conditions", "Test-condition match", "unknown",
                            "The manufacturer's test conditions are not documented.", ""))
    elif comp_issues:
        checks.append(Check("conditions", "Test-condition match", "warn",
                            "Estimates are extrapolated: " + "; ".join(comp_issues) + ".", ""))
    else:
        checks.append(Check("conditions", "Test-condition match", "pass",
                            "Rated test conditions are reasonably comparable to your feed.", ""))

    # 11. Boron -------------------------------------------------------------------
    boron_est = None
    boron_relevant = inp.target_boron_mg_l is not None or (ch.boron_mg_l is not None and inp.application in ("swro", "second_pass"))
    if boron_relevant:
        br = m.num("boron_rejection_pct")
        boron_obs = [o for o in m.observations if "boron" in (o.get("permeate_concentration_text") or "").lower()]
        if br is not None and ch.boron_mg_l is not None:
            # Same basis as the TDS estimate: average feed-side concentration along the system
            boron_avg = ch.boron_mg_l * (1.0 + ctx.cf) / 2.0
            boron_est = boron_avg * (1 - br / 100.0)
            tech["boron_estimate_mg_l"] = boron_est
            if inp.target_boron_mg_l is not None and boron_est > inp.target_boron_mg_l:
                checks.append(Check("boron", "Boron", "warn",
                                    f"Rated boron rejection ({br:g}%) suggests permeate boron of roughly {boron_est:.2f} mg/L, "
                                    f"above your {inp.target_boron_mg_l:g} mg/L target. Boron removal depends strongly on pH and temperature.",
                                    f"B_p ≈ B_avg(1−Rb) = {boron_est:.2f}"))
            else:
                checks.append(Check("boron", "Boron", "pass",
                                    f"Rated boron rejection is {br:g}% (indicative estimate {boron_est:.2f} mg/L).", ""))
        else:
            msg = "Boron rejection is not documented for this membrane."
            if boron_obs:
                msg += " Plant observations exist: " + "; ".join(o["permeate_concentration_text"] for o in boron_obs) + "."
            checks.append(Check("boron", "Boron", "unknown", msg, ""))

    # 12. Chemistry-driven conditions (system-wide) ---------------------------------
    # Pretreatment selections are recorded but never used to clear a risk: a listed antiscalant or
    # filter does not prove that a given scaling or fouling risk is controlled.
    chem = ctx.chem
    agg = [i for i in chem.items if i.key not in _PER_MEMBRANE_CHEM_KEYS]
    risk_items = [i for i in agg if i.status == "risk"]
    caution_items = [i for i in agg if i.status in ("caution", "not_assessed")]
    missing_items = [i for i in agg if i.status == "missing"]
    if inp.application in ("industrial", "other") and chem.completeness != "complete":
        checks.append(Check("chemistry", "Water chemistry", "unknown",
                            "The water analysis is insufficient for this type of application. Scaling and fouling risks must "
                            "be characterised before a membrane can be recommended.",
                            "Missing core chemistry: " + ", ".join(chem.missing_core), True))
    elif risk_items or caution_items:
        parts = []
        if risk_items:
            parts.append("risks needing pretreatment or recovery limits: " + ", ".join(i.label.lower() for i in risk_items))
        if caution_items:
            parts.append("unresolved items: " + ", ".join(i.label.lower() for i in caution_items))
        if missing_items:
            parts.append("not screened: " + ", ".join(i.label.lower() for i in missing_items))
        checks.append(Check("chemistry", "Water chemistry", "warn", "Water chemistry — " + "; ".join(parts) + ".", ""))
    elif missing_items:
        checks.append(Check("chemistry", "Water chemistry", "unknown",
                            "Some scaling or fouling risks were not screened because data are missing: "
                            + ", ".join(i.label.lower() for i in missing_items) + ".",
                            "Missing core: " + (", ".join(chem.missing_core) or "none")))
    else:
        checks.append(Check("chemistry", "Water chemistry", "pass", "No major chemistry risk identified in the screened parameters.", ""))

    # 13. Application-level caps -----------------------------------------------------
    if inp.application == "industrial":
        checks.append(Check("service_cap", "Service conditions", "warn",
                            "Wastewater and reuse feeds vary widely; pilot testing is needed before final selection.", ""))
    elif inp.application == "other":
        checks.append(Check("service_cap", "Service conditions", "warn",
                            "Specialised applications are outside the validated scope of this tool; expert review is required.", ""))
    for c in ctx.checks:
        if c.key == "calc_range":
            checks.append(Check("calc_range", c.label, "warn", c.message, c.detail))
        elif c.status == "fail":
            # A system-level hard failure (feed availability, osmotic floor) applies to every candidate.
            checks.append(Check(c.key, c.label, "fail", c.message, c.detail, True))

    # Status ---------------------------------------------------------------------
    fails = [c for c in checks if c.status == "fail"]
    crit_unknown = [c for c in checks if c.status == "unknown" and c.critical]
    unknowns = [c for c in checks if c.status == "unknown"]
    warns = [c for c in checks if c.status == "warn"]
    if fails:
        status = "unsuitable"
    elif crit_unknown:
        status = "insufficient_evidence"
    elif warns or unknowns:
        status = "conditional"
    else:
        status = "suitable"

    # Evidence quality
    crit_params = ["max_operating_pressure_bar", "max_operating_temperature_c", "rated_salt_rejection_pct", "test_nacl_mg_l",
                   "test_pressure_bar"]
    crit_params.append("rated_flux_lmh" if m.get("rated_flux_lmh") else "rated_permeate_flow_m3d")
    present = [m.get(k) for k in crit_params if m.get(k)]
    verified = sum(1 for p in present if p.verification_status == "verified")
    if present and verified == len(present) and len(present) == len(crit_params):
        evidence_level = "Verified manufacturer datasheet"
    elif present:
        evidence_level = "Secondary literature" if verified == 0 else "Partly verified"
    else:
        evidence_level = "Very limited"
    cond_distance = abs(math.log(ctx.c_avg / test_c)) if test_c else float("inf")

    if status == "unsuitable":
        summary = fails[0].message
    elif status == "insufficient_evidence":
        summary = crit_unknown[0].message
    elif status == "conditional":
        summary = "Meets documented limits checked, subject to: " + "; ".join(
            c.label.lower() for c in (warns + unknowns)[:4]) + "."
    else:
        summary = "Meets every documented limit checked, with comparable rated test conditions."

    rated = {k: _param_view(m, k) for k, _ in RATED_KEYS}
    test_text = next((p.test_conditions for p in m.params.values() if p.test_conditions and p.parameter.startswith("rated")), None)

    return {
        "membrane_id": m.id,
        "name": m.name,
        "manufacturer": m.manufacturer,
        "model": m.model,
        "category": m.category,
        "category_label": cat_label,
        "element_size": m.element_size,
        "status": status,
        "status_label": STATUS_LABELS[status],
        "summary": summary,
        "positives": positives,
        "concerns": concerns,
        "checks": [c.as_dict() for c in checks],
        "rated": rated,
        "rated_test_conditions": test_text,
        "conflicts": sorted(m.conflicts.keys()),
        "estimates": {
            "required_pressure_bar": None if p_req is None else round(p_req, 1),
            "required_pressure_high_bar": None if p_req_high is None else round(p_req_high, 1),
            "permeate_tds_mg_l": None if cp is None else round(cp, 1),
            "permeate_tds_high_mg_l": None if cp_high is None else round(cp_high, 1),
            "permeate_confidence": None if cp is None else ("rough" if comparable else "low"),
            "boron_permeate_mg_l": None if boron_est is None else round(boron_est, 2),
            "elements_required": elements,
            "rated_flux_lmh": None if flux is None else round(flux, 1),
        },
        "evidence": {
            "level": evidence_level,
            "verified_critical_params": verified,
            "critical_params_total": len(crit_params),
            "condition_match": "comparable" if comparable else ("not comparable" if comparable is False else "unknown"),
            "observations": [
                {k: o.get(k) for k in ("evidence_type", "feed_description", "performance_text", "permeate_concentration_text",
                                        "test_method", "source_id")} for o in m.observations
            ],
        },
        "source_ids": sorted(m.source_ids()),
        "technical": tech,
        "_sort": (STATUS_ORDER[status], len(unknowns) + len(warns), len(unknowns),
                  _priority_metric(inp.priority, cp, flux, p_req, A),
                  -verified, cond_distance, m.name),
    }


def _priority_metric(priority: str, cp, flux, p_req, A) -> float:
    inf = float("inf")
    if priority == "quality":
        return cp if cp is not None else inf
    if priority == "productivity":
        return -flux if flux is not None else inf
    if priority == "low_pressure":
        if p_req is not None:
            return p_req
        return -A if A is not None else inf
    return 0.0


ASSUMPTIONS = [
    "Osmotic pressure is estimated by treating dissolved solids as sodium chloride; mixed or multivalent-ion waters can differ materially.",
    "Pressure estimates use an apparent membrane permeability derived from the manufacturer's rated test point. Concentration "
    "polarization, temperature effects on permeability and (unless you entered an allowance) pressure losses are not modelled.",
    "The upper end of each pressure range reflects elements delivering up to 15% less flow than rated, as manufacturers allow.",
    "Permeate quality is a rough estimate from rated sodium chloride rejection applied to the average feed-side salinity. "
    "Individual ions such as boron, silica and nitrate are rejected differently.",
    "Concentrate salinity is an idealised mass balance that ignores precipitation and changes along the pressure vessel.",
    "All estimates describe new, clean membranes; fouling, scaling and ageing reduce performance over time.",
    "Membrane permeability is not corrected for temperature: no temperature-correction coefficients are documented in the "
    "dataset's sources. Cold feed water generally needs more pressure than estimated; warm feed water passes more salt.",
    "Element count is rounded up, so pressure is estimated at the resulting average flux (at or below your design flux). "
    "Element arrangement (stages, vessels) is not designed.",
    "Pretreatment you listed is recorded but is not assumed to control any scaling or fouling risk.",
    "Element counts are membrane-level screening estimates. They are not a plant configuration: vessel count, vessel "
    "length, staging, footprint and cost have not been assessed, and a very large count of small elements may be "
    "impractical even where every documented limit is met.",
]

LIMITATIONS = [
    "This is preliminary design support. It is not a substitute for manufacturer projection software, pilot testing or detailed engineering.",
    "Predicted values are indicative and are not guaranteed to match any real installation.",
    "Software tests confirm the calculations are implemented as documented; they do not validate the model against plant performance.",
]

UNAVAILABLE = [
    "Multi-stage and pressure-vessel modelling (pressure drop and salinity change along each vessel)",
    "Temperature correction of membrane permeability",
    "Activity-corrected calcium sulfate saturation (only a conservative upper-bound screen is applied), barium/strontium sulfate and calcium fluoride saturation",
    "Ion-by-ion permeate quality",
    "Pump power and specific energy consumption",
    "Recovery optimisation and fouling-rate prediction",
]


def methodology() -> list[dict]:
    """Calculation methodology for the technical appendix and admin console (not the client dashboard)."""
    return [
        {"title": "Flow balance", "equation": "Qf = Qp / r ;  Qc = Qf − Qp",
         "note": "r is recovery as a fraction, 0 < r < 1. Closure Qf = Qp + Qc is verified in automated tests."},
        {"title": "Salt rejection", "equation": "R = 100 × (1 − Cp / Cf)", "note": "Cf and Cp must be comparable concentrations."},
        {"title": "Approximate permeate concentration", "equation": "Cp ≈ C_avg × (1 − R/100),  C_avg = (Cf + Cf/(1−r)) / 2",
         "note": "Rough estimate using rated NaCl rejection; range uses stabilised and minimum rejection."},
        {"title": "Osmotic pressure (screening)", "equation": "π = 2 · (TDS / 58.443 g/mol) · R · (T + 273.15)",
         "note": "Ideal van 't Hoff, NaCl-equivalent. Validated correlations (Nayar et al., 2016) are recommended for design."},
        {"title": "Water flux (solution-diffusion)", "equation": "Jw = A × (ΔP − Δπ)", "note": "Kim & Hoek (2005); Li (2019)."},
        {"title": "Apparent permeance from rating", "equation": "A = J_rated / (P_test − π_avg,test)",
         "note": "J_rated = rated flow / area (LMH). π_avg,test from test salinity and recovery. Calculated value, not a manufacturer coefficient."},
        {"title": "Indicative feed pressure", "equation": "P ≈ max(J_op / A + π_avg, π_conc) + losses,  J_op = Qp / (N·Am)",
         "note": f"Range uses A and {ELEMENT_FLOW_TOLERANCE:.2f}·A. Marginal if within {PRESSURE_MARGIN_FRACTION:.0%} of available pressure."},
        {"title": "Permeate flow / element count", "equation": "Qp = Jw × Am × 24 / 1000 ;  N = ceil(Qp,target / Qp,element)",
         "note": "Element count is indicative and ignores staging. Oversized if J_op < 2/3 of design flux."},
        {"title": "Recovery per element (uniform series array)", "equation": "r_el = 1 − (1 − r)^(1/N);  r_el,max = 1/(1 + Qc/Qp,min)",
         "note": "Limit used only where the datasheet states a minimum concentrate-to-permeate ratio; otherwise reported as unknown."},
        {"title": "Per-element feed flow", "equation": "Qf / N <= Fmax (any arrangement);  uniform array: Qf / n_p <= Fmax with r_el(n_s) <= r_el,max",
         "note": "Qf/N > Fmax is a hard failure (no arrangement of N elements can comply). Failing to find a uniform array is a caution only, because staged designs differ."},
        {"title": "Calcium sulfate screen basis", "equation": "Low only if IAP_ideal(bulk, CF) x 4 <= Ksp(25 °C) and 5 <= T <= 45 °C",
         "note": "x4 is a POLICY allowance for concentration polarisation and Ksp(T), which are not modelled; otherwise unresolved."},
        {"title": "Concentrate (idealised)", "equation": "CF = 1/(1 − r) ;  Cc = (Cf − r·Cp)/(1 − r)",
         "note": "Ignores precipitation, CP and changing rejection."},
        {"title": "Calcium carbonate scaling", "equation": "LSI = pH − pHs (Langelier)",
         "note": "Applied only for TDS ≤ 10,000 mg/L; feed pH assumed in concentrate."},
        {"title": "Calcium sulfate (conservative screen)", "equation": "IAP_ideal = [Ca]·CF × [SO4]·CF  vs  Ksp,gypsum(25 °C) = 10^−4.58",
         "note": "Concentrations in mol/L with activity coefficients = 1 (an upper bound). Below Ksp → undersaturated; otherwise inconclusive."},
        {"title": "Water-analysis consistency", "equation": "Σ ions ≤ 1.15·TDS ;  |Σcations − Σanions| / (Σcations + Σanions) ≤ 10% (meq/L)",
         "note": "Screening thresholds chosen for this software; inconsistencies make candidates conditional."},
        {"title": "Ranking", "equation": "exclude unsuitable / insufficient evidence; then lexicographic: tier, open issues, unknowns, priority metric, evidence, condition distance",
         "note": "No weighted score. Tier is never overridden by priority."},
    ]


def assess(inp: AssessmentInput, membranes: list[MembraneEvidence], sources: dict[int, dict] | None = None) -> dict:
    ctx = build_system(inp)
    evaluated = [evaluate(m, ctx) for m in membranes]
    evaluated.sort(key=lambda c: c["_sort"])
    # Hard failures and unresolved critical evidence are excluded BEFORE ranking: only suitable / conditional
    # candidates receive a rank. The others keep a stable display order but no rank.
    rank = 0
    for c in evaluated:
        c.pop("_sort")
        if c["status"] in ("suitable", "conditional"):
            rank += 1
            c["rank"] = rank
        else:
            c["rank"] = None

    viable = [c for c in evaluated if c["status"] in ("suitable", "conditional")]
    recommended = viable[0] if viable and not ctx.hard_fail else None
    alternatives = [c for c in viable if c is not recommended][:5] if not ctx.hard_fail else []
    needs_data = [c for c in evaluated if c["status"] == "insufficient_evidence"]
    excluded = [c for c in evaluated if c["status"] == "unsuitable"]

    sys_fail = [c for c in ctx.checks if c.status == "fail"]
    if recommended:
        outcome = "recommended"
        if recommended["status"] == "suitable":
            headline = f"{recommended['name']} is suitable for preliminary evaluation"
        else:
            headline = f"{recommended['name']} is the best-supported candidate, subject to conditions"
        summary = recommended["summary"]
    else:
        outcome = "no_supported_recommendation"
        headline = "No supported recommendation"
        if sys_fail:
            summary = " ".join(c.message for c in sys_fail)
        elif needs_data and not viable:
            summary = ("No membrane passed every check with sufficient evidence. Some candidates could not be assessed "
                       "because key specifications or water-analysis data are missing.")
        else:
            summary = "Every membrane in the dataset fails at least one hard constraint for these conditions."

    # Client warnings (plain language)
    warnings: list[dict] = []
    for c in ctx.checks:
        if c.status == "fail":
            warnings.append({"severity": "critical", "title": c.label, "message": c.message})
        elif c.status == "warn":
            warnings.append({"severity": "caution", "title": c.label, "message": c.message})
    for item in ctx.chem.items:
        if item.status == "risk":
            warnings.append({"severity": "critical" if item.key in ("oxidant", "sdi") else "caution",
                             "title": item.label, "message": item.message})
        elif item.status in ("caution", "missing"):
            warnings.append({"severity": "caution", "title": item.label, "message": item.message})
        elif item.status == "not_assessed":
            warnings.append({"severity": "info", "title": item.label, "message": item.message})
    if inp.input_origin == "demo":
        warnings.insert(0, {"severity": "caution", "title": "Demonstration data",
                            "message": "These results are based on a built-in demonstration example (possibly edited), not a "
                                       "measured water analysis. Do not use them for a real project."})
    counted = [c for c in viable if c["estimates"]["elements_required"]]
    if len(counted) >= 2:
        lo = min(counted, key=lambda c: c["estimates"]["elements_required"])
        hi = max(counted, key=lambda c: c["estimates"]["elements_required"])
        if lo["estimates"]["elements_required"] != hi["estimates"]["elements_required"]:
            def _desc(c):
                size = f", {c['element_size']}" if c["element_size"] else ""
                return f"{c['estimates']['elements_required']:,} × {c['model']}{size}"
            warnings.append({"severity": "info", "title": "Element counts differ between candidates",
                             "message": f"The ranked candidates need between {_desc(lo)} and {_desc(hi)} elements "
                                        "(membrane-level estimates). Element count, vessel count, footprint and cost are "
                                        "not used in the ranking and must be weighed in detailed design."})
    if inp.design_flux_lmh is None:
        warnings.append({"severity": "info", "title": "Design flux not specified",
                         "message": "Operating pressure and element count were not estimated because no design flux was entered."})

    fb = ctx.flow
    cp_ref = recommended["estimates"]["permeate_tds_mg_l"] if recommended else None
    cc_mb = concentrate_concentration_mass_balance(inp.feed_tds_mg_l, cp_ref, inp.recovery) if cp_ref is not None else None

    used_source_ids = sorted({sid for c in evaluated for sid in c["source_ids"]})
    src_list = [sources[s] for s in used_source_ids if sources and s in sources]

    return {
        "engine_version": ENGINE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "outcome": outcome,
        "headline": headline,
        "summary": summary,
        "application": inp.application,
        "application_label": APPLICATION_LABELS[inp.application],
        "input_origin": inp.input_origin,
        "priority_label": PRIORITY_LABELS[inp.priority],
        "recommended": recommended,
        "alternatives": alternatives,
        "needs_more_data": needs_data,
        "excluded": excluded,
        "candidates": evaluated,
        "system": {
            "flow": {"permeate_m3d": fb.permeate_m3d, "feed_m3d": fb.feed_m3d, "concentrate_m3d": fb.concentrate_m3d,
                     "permeate_m3h": m3d_to_m3h(fb.permeate_m3d), "feed_m3h": m3d_to_m3h(fb.feed_m3d),
                     "concentrate_m3h": m3d_to_m3h(fb.concentrate_m3d), "recovery_pct": inp.recovery_pct},
            "concentrate_tds_ideal_mg_l": ctx.cc_ideal,
            "concentrate_tds_mass_balance_mg_l": cc_mb,
            "concentration_factor": ctx.cf,
            "pressure_status": next((c.status for c in ctx.checks if c.key == "osmotic_floor"), None),
            "checks": [c.as_dict() for c in ctx.checks],
        },
        "chemistry": ctx.chem.as_dict(),
        "warnings": warnings,
        "assumptions": ASSUMPTIONS,
        "limitations": LIMITATIONS,
        "unavailable": UNAVAILABLE,
        "sources": src_list,
        "technical": {
            "osmotic_feed_bar": ctx.pi_feed, "osmotic_avg_bar": ctx.pi_avg, "osmotic_concentrate_bar": ctx.pi_conc,
            "avg_feed_side_tds_mg_l": ctx.c_avg, "pressure_loss_allowance_bar": ctx.loss,
            "flow_closure_error_m3d": fb.closure_error,
            "policy": {"pressure_margin_fraction": PRESSURE_MARGIN_FRACTION, "element_flow_tolerance": ELEMENT_FLOW_TOLERANCE,
                       "comparable_salinity_ratio": COMPARABLE_SALINITY_RATIO,
                       "comparable_temperature_delta_c": COMPARABLE_TEMPERATURE_DELTA_C},
        },
    }


def client_view(result: dict) -> dict:
    """Strip internal calculation details for the client dashboard.

    Removes ``technical`` blocks and the technical ``detail`` text of each check,
    leaving plain-language messages, statuses, estimates and sources.
    """
    import copy

    r = copy.deepcopy(result)
    r.pop("technical", None)

    def clean_candidate(c: dict | None) -> None:
        if not c:
            return
        c.pop("technical", None)
        for chk in c.get("checks", []):
            chk.pop("detail", None)
            chk.pop("critical", None)

    clean_candidate(r.get("recommended"))
    for key in ("alternatives", "needs_more_data", "excluded", "candidates"):
        for c in r.get(key, []):
            clean_candidate(c)
    for chk in r.get("system", {}).get("checks", []):
        chk.pop("detail", None)
        chk.pop("critical", None)
    chem = r.get("chemistry", {})
    for item in chem.get("items", []):
        item.pop("detail", None)
    chem.pop("lsi_feed", None)
    chem.pop("lsi_concentrate", None)
    return r
