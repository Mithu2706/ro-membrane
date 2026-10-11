"""Feed-water chemistry screening.

Produces plain-language risk items. Thresholds marked ``POLICY`` are screening
rules chosen for this software (documented in the methodology), not membrane
specifications. Where a reliable index cannot be computed, the item is reported
as "not assessed" rather than guessed.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .hydraulics import concentration_factor_ideal
from .inputs import AssessmentInput
from .units import calcium_as_caco3, magnesium_as_caco3

# POLICY thresholds -------------------------------------------------------------
LSI_MAX_TDS_MG_L = 10000.0  # Langelier index is a fresh/brackish-water index; not applied above this TDS
SILICA_SCREEN_MG_L = 100.0  # commonly cited order of amorphous-silica solubility near 25 °C, neutral pH
HARDNESS_CONSISTENCY_TOL = 0.20  # 20% mismatch between entered and computed hardness triggers a data-check note
SWRO_LOW_TDS_MG_L = 10000.0  # SWRO selected but feed TDS unusually low
BWRO_HIGH_TDS_MG_L = 15000.0  # BWRO selected but feed TDS unusually high
SDI_GENERAL_LIMIT = 5.0  # highest maximum-SDI value found in the verified datasheets
ION_SUM_TOL = 0.15  # sum of reported ions may exceed TDS by up to 15% (bicarbonate partly lost in TDS residue)
ION_BALANCE_TOL = 0.10  # lenient screening threshold for cation/anion imbalance

# Constants (standard values, not membrane data)
CA_MOLAR_MASS = 40.078
SO4_MOLAR_MASS = 96.06
CACO3_MOLAR_MASS = 100.087
ALK_TO_HCO3 = 61.017 / 50.04  # mg/L as CaCO3 -> mg/L as HCO3- (bicarbonate-dominated range)
GYPSUM_KSP_25C = 10 ** -4.58  # gypsum solubility product at 25 °C (log K = -4.58, PHREEQC/WATEQ databases)
# POLICY: the gypsum screen only reports "low" when the ideal bulk-concentrate ion product is at most 1/4 of Ksp(25 °C).
# The x4 headroom is an allowance for effects that RAISE saturation but are not modelled here: concentration
# polarisation at the membrane surface (squared, because it multiplies both ions) and the temperature dependence of
# Ksp. It is a screening allowance, not a measured bound; anything above it is reported as unresolved.
GYPSUM_SCREEN_HEADROOM = 4.0
GYPSUM_SCREEN_T_RANGE_C = (5.0, 45.0)  # outside this feed temperature range the screen does not conclude


@dataclass
class ChemItem:
    key: str
    label: str
    status: str  # ok | caution | risk | not_assessed | missing
    message: str
    detail: str = ""

    def as_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class ChemistryResult:
    completeness: str  # complete | partial | insufficient
    missing_core: list[str]
    items: list[ChemItem] = field(default_factory=list)
    lsi_feed: float | None = None
    lsi_concentrate: float | None = None
    concentration_factor: float | None = None

    @property
    def has_risk(self) -> bool:
        return any(i.status == "risk" for i in self.items)

    @property
    def has_caution(self) -> bool:
        return any(i.status in ("caution", "not_assessed") for i in self.items)

    def as_dict(self) -> dict:
        return {
            "completeness": self.completeness,
            "missing_core": self.missing_core,
            "items": [i.as_dict() for i in self.items],
            "lsi_feed": self.lsi_feed,
            "lsi_concentrate": self.lsi_concentrate,
            "concentration_factor": self.concentration_factor,
        }


def langelier_index(ph: float, tds_mg_l: float, temperature_c: float, calcium_caco3: float,
                    alkalinity_caco3: float) -> float | None:
    """Langelier Saturation Index, LSI = pH − pHs (Langelier, 1936; ASTM D3739 form).

    pHs = (9.3 + A + B) − (C + D)
      A = (log10 TDS − 1)/10, B = −13.12 log10(T + 273) + 34.55,
      C = log10(Ca as CaCO3) − 0.4, D = log10(alkalinity as CaCO3).
    """
    if min(tds_mg_l, calcium_caco3, alkalinity_caco3) <= 0:
        return None
    a = (math.log10(tds_mg_l) - 1.0) / 10.0
    b = -13.12 * math.log10(temperature_c + 273.0) + 34.55
    c = math.log10(calcium_caco3) - 0.4
    d = math.log10(alkalinity_caco3)
    phs = (9.3 + a + b) - (c + d)
    return ph - phs


def screen(inp: AssessmentInput) -> ChemistryResult:
    ch = inp.chemistry
    cf = concentration_factor_ideal(inp.recovery)
    items: list[ChemItem] = []

    calcium_caco3 = calcium_as_caco3(ch.calcium_mg_l) if ch.calcium_mg_l is not None else None
    hardness_known = ch.hardness_mg_l_caco3 is not None or ch.calcium_mg_l is not None

    # Core completeness: pH, calcium or hardness, alkalinity, SDI or turbidity
    missing = []
    if ch.ph is None:
        missing.append("pH")
    if not hardness_known:
        missing.append("calcium or total hardness")
    if ch.alkalinity_mg_l_caco3 is None:
        missing.append("alkalinity")
    if ch.sdi is None and ch.turbidity_ntu is None:
        missing.append("SDI or turbidity")
    completeness = "complete" if not missing else ("partial" if len(missing) <= 2 else "insufficient")
    if missing:
        items.append(ChemItem(
            "chemistry_completeness", "Water analysis completeness", "missing",
            "Some key water-analysis values were not provided (" + ", ".join(missing) + "). Scaling and fouling "
            "risks cannot be fully screened until they are measured.",
            "Core screening set: pH, Ca or hardness, alkalinity, SDI or turbidity."))

    # Application / salinity consistency (warning only - never used to pick a category)
    if inp.application == "swro" and inp.feed_tds_mg_l < SWRO_LOW_TDS_MG_L:
        items.append(ChemItem("salinity_fit", "Salinity vs. application", "caution",
                              "Seawater RO was selected but the feed salinity is unusually low for seawater. "
                              "Confirm the application before relying on the results.",
                              f"Feed TDS {inp.feed_tds_mg_l:.0f} mg/L < POLICY {SWRO_LOW_TDS_MG_L:.0f} mg/L."))
    if inp.application == "bwro" and inp.feed_tds_mg_l > BWRO_HIGH_TDS_MG_L:
        items.append(ChemItem("salinity_fit", "Salinity vs. application", "caution",
                              "Brackish-water RO was selected but the feed salinity is high for brackish water. "
                              "Osmotic pressure may exceed what brackish elements are rated for.",
                              f"Feed TDS {inp.feed_tds_mg_l:.0f} mg/L > POLICY {BWRO_HIGH_TDS_MG_L:.0f} mg/L."))

    # Calcium carbonate scaling
    lsi_feed = lsi_conc = None
    ca_for_lsi = calcium_caco3
    ca_basis = "calcium"
    if ca_for_lsi is None and ch.hardness_mg_l_caco3 is not None:
        ca_basis = "total hardness (upper bound for calcium)"
        ca_for_lsi = ch.hardness_mg_l_caco3
    if ch.ph is not None and ca_for_lsi is not None and ch.alkalinity_mg_l_caco3 is not None:
        if inp.feed_tds_mg_l > LSI_MAX_TDS_MG_L:
            items.append(ChemItem("caco3", "Calcium carbonate scaling", "not_assessed",
                                  "Carbonate scaling was not scored because the simple index used here is not valid at "
                                  "this salinity. A detailed projection (e.g. Stiff & Davis index) is needed.",
                                  f"LSI not applied above POLICY TDS {LSI_MAX_TDS_MG_L:.0f} mg/L."))
        else:
            lsi_feed = langelier_index(ch.ph, inp.feed_tds_mg_l, inp.feed_temperature_c, ca_for_lsi,
                                       ch.alkalinity_mg_l_caco3)
            lsi_conc = langelier_index(ch.ph, inp.feed_tds_mg_l * cf, inp.feed_temperature_c, ca_for_lsi * cf,
                                       ch.alkalinity_mg_l_caco3 * cf)
            if lsi_conc is None:
                items.append(ChemItem("caco3", "Calcium carbonate scaling", "not_assessed",
                                      "Carbonate scaling could not be scored from the values supplied (a zero calcium or "
                                      "alkalinity value).", "LSI undefined for zero Ca or alkalinity."))
            elif lsi_conc > 0:
                items.append(ChemItem("caco3", "Calcium carbonate scaling", "risk",
                                      "Calcium carbonate is likely to precipitate in the concentrate at the target recovery. "
                                      "Antiscalant dosing and/or pH adjustment should be evaluated, or recovery reduced.",
                                      f"LSI feed {lsi_feed:.2f}; concentrate {lsi_conc:.2f} (idealised CF {cf:.2f}, feed pH "
                                      f"assumed in concentrate; Ca basis: {ca_basis})."))
            else:
                items.append(ChemItem("caco3", "Calcium carbonate scaling", "ok",
                                      "Calcium carbonate scaling tendency appears low at the target recovery.",
                                      f"LSI feed {lsi_feed:.2f}; concentrate {lsi_conc:.2f} (idealised CF {cf:.2f})."))

    # Silica
    if ch.silica_mg_l is not None:
        conc_si = ch.silica_mg_l * cf
        if conc_si > SILICA_SCREEN_MG_L:
            items.append(ChemItem("silica", "Silica", "risk",
                                  "Silica could approach its solubility limit in the concentrate. Recovery may need to be "
                                  "limited or a silica-specific antiscalant evaluated. Calcium and magnesium can worsen "
                                  "silica fouling.",
                                  f"Concentrate SiO2 ≈ {conc_si:.0f} mg/L (idealised) > POLICY screen {SILICA_SCREEN_MG_L:.0f} mg/L."))
        else:
            items.append(ChemItem("silica", "Silica", "ok", "Silica appears manageable at the target recovery.",
                                  f"Concentrate SiO2 ≈ {conc_si:.0f} mg/L (idealised)."))

    if ch.silica_mg_l is None:
        items.append(ChemItem("silica", "Silica", "missing",
                              "Silica was not measured, so silica scaling was not screened.", "SiO2 not provided."))

    # Calcium sulfate (gypsum) screen.
    # Basis: bulk concentrate at the target recovery with complete salt rejection (CF = 1/(1-r), an upper bound on
    # bulk concentrate concentration); concentrations in mol/L used in place of molality (differs by a few % at
    # seawater-concentrate strength); activity coefficients taken as 1. Activity coefficients and ion pairing
    # (CaSO4 aq) both LOWER the true ion activity product, so the ideal product over-estimates bulk saturation.
    # NOT modelled, and able to RAISE saturation: concentration polarisation at the membrane surface and the
    # temperature dependence of Ksp (Ksp at 25 °C is used). Hence the result is never reported as "safe": it is
    # "low (screening level)" only with the POLICY headroom and within the temperature range, otherwise unresolved.
    ca_mol = None
    ca_basis_s = "calcium"
    if ch.calcium_mg_l is not None:
        ca_mol = ch.calcium_mg_l / 1000.0 / CA_MOLAR_MASS
    elif ch.hardness_mg_l_caco3 is not None:
        ca_mol = ch.hardness_mg_l_caco3 / 1000.0 / CACO3_MOLAR_MASS
        ca_basis_s = "total hardness (upper bound for calcium)"
    if ch.sulfate_mg_l is None:
        items.append(ChemItem("sulfate", "Calcium sulfate scaling", "missing",
                              "Sulfate was not measured, so calcium sulfate (gypsum) scaling was not screened.",
                              "SO4 not provided."))
    elif ca_mol is None:
        items.append(ChemItem("sulfate", "Calcium sulfate scaling", "missing",
                              "Calcium (or hardness) was not measured, so calcium sulfate scaling was not screened.",
                              "Ca/hardness not provided."))
    else:
        so4_mol = ch.sulfate_mg_l / 1000.0 / SO4_MOLAR_MASS
        iap_ideal = (ca_mol * cf) * (so4_mol * cf)
        ratio = iap_ideal / GYPSUM_KSP_25C
        tlo, thi = GYPSUM_SCREEN_T_RANGE_C
        basis = (f"Ideal bulk-concentrate IAP/Ksp(25 °C) = {ratio:.2f}; CF {cf:.2f}; Ca basis: {ca_basis_s}; "
                 f"POLICY headroom x{GYPSUM_SCREEN_HEADROOM:g}; CP and Ksp(T) not modelled.")
        if not tlo <= inp.feed_temperature_c <= thi:
            items.append(ChemItem("sulfate", "Calcium sulfate scaling", "not_assessed",
                                  "Calcium sulfate scaling is unresolved: the simplified screen is not applied at this feed "
                                  "temperature. A detailed projection is needed.",
                                  basis + f" Feed T {inp.feed_temperature_c:g} °C outside {tlo:g}-{thi:g} °C."))
        elif ratio * GYPSUM_SCREEN_HEADROOM <= 1.0:
            items.append(ChemItem("sulfate", "Calcium sulfate scaling", "ok",
                                  "Calcium sulfate (gypsum) appears well below saturation on a simplified screen. This is a "
                                  "screening indication, not a saturation calculation.", basis))
        elif ratio < 1.0:
            items.append(ChemItem("sulfate", "Calcium sulfate scaling", "not_assessed",
                                  "Calcium sulfate scaling is unresolved: the simplified estimate is below saturation, but not "
                                  "by enough to allow for effects this screen does not model (concentration at the membrane "
                                  "surface, temperature). A detailed projection is needed.", basis))
        else:
            items.append(ChemItem("sulfate", "Calcium sulfate scaling", "not_assessed",
                                  "Calcium sulfate scaling is unresolved: the simplified estimate reaches or exceeds saturation. "
                                  "A detailed projection with activity corrections is needed; antiscalant or lower recovery "
                                  "may be required.", basis))

    # Data consistency ------------------------------------------------------------
    if ch.hardness_mg_l_caco3 is not None and ch.calcium_mg_l is not None and ch.magnesium_mg_l is not None:
        computed = calcium_as_caco3(ch.calcium_mg_l) + magnesium_as_caco3(ch.magnesium_mg_l)
        if ch.hardness_mg_l_caco3 > 0 and abs(computed - ch.hardness_mg_l_caco3) / ch.hardness_mg_l_caco3 > HARDNESS_CONSISTENCY_TOL:
            items.append(ChemItem("hardness_check", "Data consistency: hardness", "caution",
                                  "The total hardness entered does not match the calcium and magnesium values. Please "
                                  "check the water analysis.",
                                  f"Computed hardness {computed:.0f} vs entered {ch.hardness_mg_l_caco3:.0f} mg/L as CaCO3."))
    elif ch.hardness_mg_l_caco3 is not None and ch.calcium_mg_l is not None:
        if calcium_as_caco3(ch.calcium_mg_l) > ch.hardness_mg_l_caco3 * (1 + HARDNESS_CONSISTENCY_TOL):
            items.append(ChemItem("hardness_check", "Data consistency: hardness", "caution",
                                  "Calcium alone exceeds the total hardness entered, which is not physically possible. "
                                  "Please check the water analysis.",
                                  f"Ca as CaCO3 {calcium_as_caco3(ch.calcium_mg_l):.0f} > hardness {ch.hardness_mg_l_caco3:.0f}."))

    ions = {"calcium": ch.calcium_mg_l, "magnesium": ch.magnesium_mg_l, "sodium": ch.sodium_mg_l,
            "chloride": ch.chloride_mg_l, "sulfate": ch.sulfate_mg_l, "silica": ch.silica_mg_l, "boron": ch.boron_mg_l}
    known = {k: v for k, v in ions.items() if v is not None}
    over = [k for k, v in known.items() if v > inp.feed_tds_mg_l]
    ion_sum = sum(known.values()) + (ch.alkalinity_mg_l_caco3 or 0.0) * ALK_TO_HCO3
    if over:
        items.append(ChemItem("ion_sum", "Data consistency: ions vs TDS", "caution",
                              "Some individual ion concentrations exceed the feed TDS (" + ", ".join(over) + "). Please check "
                              "the units and values.", f"TDS {inp.feed_tds_mg_l:.0f} mg/L."))
    elif known and ion_sum > inp.feed_tds_mg_l * (1 + ION_SUM_TOL):
        items.append(ChemItem("ion_sum", "Data consistency: ions vs TDS", "caution",
                              "The ion concentrations entered add up to more than the feed TDS. Please check the water analysis.",
                              f"Sum of ions ≈ {ion_sum:.0f} mg/L (alkalinity as HCO3) vs TDS {inp.feed_tds_mg_l:.0f} mg/L "
                              f"(POLICY tolerance {ION_SUM_TOL:.0%})."))
    major = (ch.calcium_mg_l, ch.magnesium_mg_l, ch.sodium_mg_l, ch.chloride_mg_l, ch.sulfate_mg_l, ch.alkalinity_mg_l_caco3)
    if all(v is not None for v in major):
        cations = ch.calcium_mg_l / 20.04 + ch.magnesium_mg_l / 12.15 + ch.sodium_mg_l / 22.99
        anions = ch.chloride_mg_l / 35.45 + ch.sulfate_mg_l / 48.03 + ch.alkalinity_mg_l_caco3 / 50.04
        if cations + anions > 0:
            imbalance = abs(cations - anions) / (cations + anions)
            if imbalance > ION_BALANCE_TOL:
                items.append(ChemItem("ion_balance", "Data consistency: ion balance", "caution",
                                      "The major cations and anions do not balance, which suggests an incomplete or "
                                      "inconsistent water analysis.",
                                      f"Cations {cations:.2f} meq/L vs anions {anions:.2f} meq/L; imbalance {imbalance:.1%} "
                                      f"> POLICY {ION_BALANCE_TOL:.0%}."))

    # Particulate fouling
    if ch.sdi is not None and ch.sdi > SDI_GENERAL_LIMIT:
        items.append(ChemItem("sdi", "Particulate fouling (SDI)", "risk",
                              "The silt density index is above the maximum allowed by every verified datasheet in the "
                              "dataset. Additional pretreatment is required before RO.",
                              f"SDI {ch.sdi} > {SDI_GENERAL_LIMIT}."))
    elif ch.sdi is not None:
        items.append(ChemItem("sdi", "Particulate fouling (SDI)", "ok",
                              "Silt density index is within commonly stated membrane limits; check each membrane's own limit.",
                              f"SDI {ch.sdi}."))

    # Organics
    if ch.toc_mg_l is not None or ch.cod_mg_l is not None:
        msg = ("Organic load was reported. Organic and biological fouling potential should be addressed in pretreatment "
               "design; this version does not quantify it.")
        items.append(ChemItem("organics", "Organic fouling", "caution" if inp.application in ("industrial", "other") else "not_assessed",
                              msg, f"TOC {ch.toc_mg_l} mg/L, COD {ch.cod_mg_l} mg/L."))

    # Oxidants
    if ch.oxidant_exposure == "free_chlorine_present" or (ch.free_chlorine_mg_l is not None and ch.free_chlorine_mg_l > 0):
        items.append(ChemItem("oxidant", "Chlorine / oxidants", "risk",
                              "Free chlorine reaching polyamide RO membranes causes irreversible damage. Chlorine must be "
                              "removed (dechlorination) before the RO system.",
                              f"Oxidant exposure: {ch.oxidant_exposure}; free chlorine {ch.free_chlorine_mg_l} mg/L."))
    elif ch.oxidant_exposure == "chloramine":
        items.append(ChemItem("oxidant", "Chlorine / oxidants", "caution",
                              "Chloramine exposure can still damage polyamide membranes over time, especially with metals "
                              "present. Confirm compatibility with the manufacturer.", "Oxidant exposure: chloramine."))
    elif ch.oxidant_exposure == "unknown":
        items.append(ChemItem("oxidant", "Chlorine / oxidants", "missing",
                              "Oxidant/chlorine exposure was not specified. Polyamide membranes require chlorine-free feed.",
                              "Oxidant exposure unknown."))

    # Boron
    if ch.boron_mg_l is not None and inp.target_boron_mg_l is not None and ch.boron_mg_l > inp.target_boron_mg_l:
        items.append(ChemItem("boron", "Boron", "caution",
                              "Boron must be reduced to meet your target. Boron rejection differs between membranes and "
                              "depends strongly on pH and temperature; a second pass may be required.",
                              f"Feed boron {ch.boron_mg_l} mg/L vs target {inp.target_boron_mg_l} mg/L."))
    elif ch.boron_mg_l is None and inp.target_boron_mg_l is not None:
        items.append(ChemItem("boron", "Boron", "missing",
                              "A boron target was set but feed boron was not measured, so boron compliance cannot be assessed.",
                              "Feed boron not provided."))

    return ChemistryResult(completeness=completeness, missing_core=missing, items=items, lsi_feed=lsi_feed,
                           lsi_concentrate=lsi_conc, concentration_factor=cf)
