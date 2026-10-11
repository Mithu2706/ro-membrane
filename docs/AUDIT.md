# Osmora engine audit — 2026-10-10 (engine 1.0.0 → 1.1.0, schema v2 → v3)

Scope: `backend/app/engine/*`, `backend/app/seed_data.py`, report/dashboard consistency. No UI redesign; no new
membrane specifications beyond values already read from verified datasheets.

## Confirmed defects (each reproduced against 1.0.0 before fixing)

| # | Severity | Defect | Fix | Regression test(s) |
|---|---|---|---|---|
| D1 | High | Measured turbidity with **no documented turbidity limit** passed; a documented limit with no measurement was not flagged; SDI > 5 with no documented SDI limit was only non-critical. | Every measurement needs a limit and every limit a measurement (else *unknown*); SDI above all verified datasheet limits with no documented limit is a critical unknown. | `test_d1_*` (3) |
| D2 | High | **Chloramine** exposure passed the membrane oxidant check. | Now a caution (conditional). | `test_d2_chloramine_is_not_treated_as_safe` |
| D3 | Medium | Gypsum was "not assessed" (caution) only when sulfate **was** measured; unmeasured sulfate passed silently — measuring more made results look worse. Unmeasured silica was silent. | Unmeasured sulfate/silica (and boron when a boron target is set) are explicit *missing* items → conditional. Added a conservative gypsum screen (ideal ion product vs Ksp 10^−4.58 at 25 °C; below Ksp → undersaturated, otherwise inconclusive). | `test_d3_*`, `test_gypsum_screen_inconclusive_at_seawater_sulfate`, `test_zero_is_distinct_from_missing`, `test_boron_target_without_measurement_is_explicit` |
| D4 | High | A **disputed**-only value was used as a valid limit. | Disputed rows are never used; parameter treated as missing. | `test_d4_disputed_only_limit_is_treated_as_missing` |
| D5 | High | **Calculated** (and any non-rated) values could satisfy operating limits. | Only manufacturer ratings are resolved for engine use. | `test_d5_non_rated_values_never_satisfy_limits` (4 cases) |
| D6 | High | Conflicting values for a limit from **equally verified** sources were resolved silently (could be "suitable" with 41 vs 14 bar recorded). | Ambiguous conflicts on safety parameters → critical unknown (*insufficient evidence*); conflicts resolved by better verification → caution. | `test_d6_*`, `test_conflict_resolved_by_verification_*` |
| D7 | Medium | **Low production**: 5 m³/d gave 1 element producing ~19.5 m³/d at design flux; pressure assumed design flux; 50% recovery from one element unflagged; result "suitable". | Pressure now evaluated at the implied flux of the rounded-up element count; oversized-element caution (implied flux < 2/3 design); per-element recovery checked against the datasheet 5:1 concentrate:permeate limit where documented, else *unknown* when it exceeds rated test recovery. | `test_d7_*` (2), `test_element_count_and_implied_flux_are_consistent` |
| D8 | Medium | Pressure margin computed relative to required pressure, while documented as "within 10 % of available pressure". | Margin now relative to available pressure. | `test_pressure_margin_is_relative_to_available_pressure` |
| D9 | Medium | Implausible analyses accepted silently (ions exceeding TDS, ion imbalance, Ca > hardness). | Data-consistency cautions (ion sum ≤ 1.15·TDS, single ion ≤ TDS, ion balance ≤ 10 %, Ca ≤ hardness) → conditional. Thresholds are documented screening policy. | `test_d9_*` (2), `test_calcium_exceeding_hardness_flagged`, `test_balanced_demo_analysis_not_flagged` |
| D10 | Low | Boron permeate estimate used feed boron while TDS used the average feed-side concentration (inconsistent, non-conservative). | Boron now uses the average feed-side concentration. | `test_boron_estimate_uses_average_feed_side_concentration` |
| D11 | Low | Demo inputs were indistinguishable from measured data in results, PDF and admin. | `input_origin` recorded; "Demonstration data" warning, dashboard badge, PDF banner and admin badge. | `test_demo_origin_is_flagged_in_result`, `test_pdf_and_dashboard_are_consistent` |
| D12 | Low | PDF stated pressure "at design flux" and omitted the client warning list shown on the dashboard. | PDF states the flux basis and lists every client warning. | `test_pdf_and_dashboard_are_consistent` |
| D13 | Low (data) | BW30-400/34i listed for industrial/reuse service; the datasheet only says "high fouling or challenging feed conditions". | Claim removed (migration v3). | covered by seed tests |
| D14 | Low | Ranking counted unknowns before cautions, so after D1 a candidate with three cautions outranked one with two open issues. | Rank by total open issues, then unknowns. | `test_ranking_counts_open_issues_before_unknowns` |

Checked and found correct: missing pressure/temperature limits are critical unknowns; unknown chlorine exposure is never
"suitable"; listed pretreatment never clears a risk (`test_pretreatment_does_not_clear_scaling_risk`); flow balance
closure; LMH ↔ m³/d conversions; recovery % → fraction; concentrate mass balance.

## Data added
`min_concentrate_permeate_ratio = 5` for Hydranautics SWC4+ and ESPA-2540, verbatim from the datasheets already
verified ("Minimum Ratio of Concentrate to Permeate Flow for any Element: 5:1"). Applied by migration v3 (idempotent).

## Not changed (deliberately)
* **Temperature correction** — no temperature-correction coefficients exist in the dataset's verified sources; adding a
  generic Arrhenius constant would be an unsupported coefficient. Temperature mismatch > 5 °C remains flagged, and the
  assumption is stated in every result.

## Remaining engineering limitations
* Single-element-equivalent screening; no staging, vessel pressure drop, or concentration-polarisation film model.
* Ideal NaCl-equivalent osmotic pressure; no activity-corrected CaCO3 (above 10,000 mg/L TDS), CaSO4, BaSO4, SrSO4, CaF2.
* Small-element formats can yield very large element counts (e.g. 800 × 2.5-inch); no sourced limit is used to flag this.
* Per-element feed-flow limits are stored but not checked (needs a vessel arrangement).
* Many catalogued models lack verified limits and remain *insufficient evidence*.
* Tests verify implementation against the documented method only. **No validation against independent experimental
  or plant data has been performed.**

---

# Final targeted audit — 2026-10-10 (engine 1.1.0, same schema v3)

## Confirmed defects (each reproduced before fixing)

| # | Defect | Fix | Regression tests (`tests/test_final_audit.py`) |
|---|---|---|---|
| G1 | Gypsum screen labelled an ideal ion product of 0.99 × Ksp "undersaturated, even on a conservative estimate". The bound covers activity coefficients but **not** concentration polarisation at the membrane surface, which raises saturation. | "Low (screening indication)" only if ideal bulk-concentrate IAP × 4 ≤ Ksp(25 °C); otherwise **unresolved**. The ×4 is a documented POLICY allowance for unmodelled CP and Ksp(T), not a measured bound. Wording never says "safe". | `test_g1_*` (4) |
| G2 | Gypsum screen used Ksp at 25 °C at any feed temperature without saying so. | Outside 5–45 °C the screen does not conclude (unresolved). Basis (CF, molarity-for-molality, no CP, Ksp 25 °C) stated in the technical detail. | `test_g2_outside_temperature_range_is_unresolved` (2) |
| F1 | Documented maximum feed flow per element (BW30-400/34i 19 m³/h, SWC4+ 17 m³/h, ESPA-2540 1.36 m³/h) was never checked. | Hard failure if Qf/N > Fmax (no arrangement of N elements can comply). Otherwise looks for a uniform series × parallel array meeting all documented limits: found → pass; none → caution (staged designs differ); a limit not documented (e.g. minimum concentrate flow for FilmTec sheets) → unknown. | `test_f1_*` (2), `test_minimum_concentrate_flow_undocumented_is_unknown`, `test_no_uniform_arrangement_is_caution_not_failure`, `test_arrangement_unknown_when_element_count_not_estimated`, `test_seed_hydranautics_limits_enforced` |
| R1 | A system-level hard failure (e.g. feed-water limit) left candidates labelled "suitable" with rank 1. | System hard failures are added to every candidate as hard failures. | `test_r1_system_hard_failure_applies_to_every_candidate` |
| R2 | Unsuitable and insufficient-evidence candidates received rank numbers. | Excluded before ranking: only suitable/conditional candidates are ranked; the others show "—". | `test_r2_only_viable_candidates_are_ranked`, `test_priority_cannot_promote_excluded_candidate` |
| E1 | Very different element counts between candidates (52 × 8-inch vs 800 × 2.5-inch for the brackish demo) were not visible in the ranked list or report. | No threshold invented. A factual information note states the range; element counts shown in the alternatives list and PDF table; every result states element counts are membrane-level, not a plant configuration. | `test_element_count_spread_is_reported_without_threshold`, `test_element_count_scope_is_stated` |

Ranking is unchanged in principle: ESPA-2540 still ranks first for the brackish demo because its datasheet documents
both per-element limits, while BW30-400/34i lacks a documented minimum concentrate flow. This is an evidence-based
ordering, not a judgement of plant practicality.

## Comparison with independent references

No manufacturer projection (WAVE / IMSDesign) for these elements under stated conditions was found in public sources
(DuPont's tool requires registration; the open-access FilmTec SWRO study of Casañas Gonzalez et al., 2026 could not be
retrieved — HTTP 403). The available comparisons are below. **None of them is a validation.**

| Reference | Conditions | Engine | Observation | Assessment |
|---|---|---|---|---|
| Datasheet rated points (SW30XLE-440, BW30-400/34i, SWC4+) | Datasheet test conditions | Reproduces test pressure exactly when N divides production (test `test_rated_point_reproduction_is_internally_consistent`) | — | **Circular** consistency check only: the permeance is derived from the same point. |
| Ansari et al. (2021), pilot, BW30-400 (via review Fig. 9) | 1,000 ppm feed (12 ppm permeate at 98.8 % rejection), 13 bar; recovery and temperature **not reported**; engine run with BW30-400/34i (same rated flow/rejection, different spacer and model designation) | Permeate 5.3–10.6 mg/L (10 % recovery) to 7.5–15 mg/L (50 %) | 12 mg/L, 98.8 % rejection | Partial match only (model and conditions incomplete). Observation sits at or above the upper end of the engine range → the rough permeate estimate is **optimistic**, consistent with the stated caveat. |
| Lim et al. (2024), coupon "SW30" membrane | 35,000 mg/L NaCl, 55 bar, 25 °C, cross-flow coupon | Apparent element permeance for SW30HR-380: 1.10 LMH/bar | 1.63 LMH/bar | Not comparable (coupon vs element; exact commercial model not stated). Same order of magnitude; element apparent permeance is expected to be lower (CP, pressure drop). |
| Conidi et al. (2018), ESPA-2540 | Softened FGD wastewater, 18 bar | Rated NaCl rejection 99.4 % | Na rejection ≈ 80 % | Not comparable (mixed-ion wastewater); illustrates why NaCl ratings do not transfer to such feeds. |

## Remaining limitations (final)
* No plant-level or independent model validation has been performed; tests check the implementation only.
* Gypsum: no activity model, no CP, Ksp at 25 °C only; the ×4 headroom is a policy allowance. Silica uses a fixed
  100 mg/L bulk-concentrate screen that is not temperature- or pH-dependent and is likewise not conservative at low temperature.
* Arrangement check uses idealised uniform arrays with equal recovery per element; vessel length, staging taper,
  minimum concentrate flow (where undocumented), pressure drop and recirculation are not modelled.
* Element counts are membrane-level estimates; plant practicality (vessel count, footprint, cost) is not assessed.
* No temperature correction of permeability (no coefficients in verified sources).
