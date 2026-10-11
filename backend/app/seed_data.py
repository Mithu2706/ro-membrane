"""Starter research dataset.

Sources of every value:
  * The supplied review report "_Research_Task_Evidence-Based_Reverse_Osmosis_Me.pdf"
    (Figures 8 and 9). Values taken from it are marked ``report-extracted``: the
    original paper was not re-checked.
  * Manufacturer datasheets whose text was extracted and read on 2026-10-10. These
    are marked ``verified``. A datasheet is attached ONLY to the exact model it
    names (e.g. the BW30-400/34i sheet is not attached to BW30-400).

Nothing here is filled in from memory or by analogy. Parameters that no source
supports are simply absent and are shown as "Not reported".

Pressure conversions: where a datasheet gives both psig and metric values, the
lower (more conservative) of the stated metric value and the exact psi conversion
is stored, and the verbatim text is kept in ``value_text``.
"""
from __future__ import annotations

VERIFIED_ON = "2026-10-10"

# key -> source record
SOURCES: dict[str, dict] = {
    "review": dict(
        title="RO Membrane Selection Evidence Review (supplied research report, Consensus-generated literature review)",
        authors=None,
        year=2026,
        url=None,
        source_type="review-report",
        publisher="Consensus NLP, Inc. (supplied file _Research_Task_Evidence-Based_Reverse_Osmosis_Me.pdf)",
        page_table="Figures 8-9, pp. 4-6",
        verification_status="verified",
        notes="Initial research source. Values cited from it are secondary and marked report-extracted until the original paper is checked.",
    ),
    "karan2020": dict(
        title="On the influence of salt concentration on the transport properties of reverse osmosis membranes in high pressure and high recovery desalination",
        authors="Karan, S.; Livingston, A.",
        year=2020,
        doi="10.1016/j.memsci.2019.117339",
        url="https://doi.org/10.1016/j.memsci.2019.117339",
        source_type="peer-reviewed",
        publisher="Journal of Membrane Science, 594, 117339",
        page_table="Table of commercial membranes (as reproduced in review Fig. 8)",
        verification_status="report-extracted",
        notes="Manufacturer ratings as tabulated by the authors; original table not re-checked.",
    ),
    "mostafaa2021": dict(
        title="Performance evaluation of a Sea water reverse osmosis system at different operating scenarios",
        authors="Mostafaa, M.; Moawed, M.; Refaey, H.; Salem, M.",
        year=2021,
        doi="10.21608/erjsh.2021.227492",
        url="https://doi.org/10.21608/erjsh.2021.227492",
        source_type="peer-reviewed",
        publisher="Engineering Research Journal - Faculty of Engineering (Shoubra)",
        page_table="System specification table (as reproduced in review Fig. 8)",
        verification_status="report-extracted",
    ),
    "ruizgarcia2021": dict(
        title="Performance evaluation and boron rejection in a SWRO system under variable operating conditions",
        authors="Ruiz-García, A.",
        year=2021,
        doi="10.1016/j.compchemeng.2021.107441",
        url="https://doi.org/10.1016/j.compchemeng.2021.107441",
        source_type="peer-reviewed",
        publisher="Computers & Chemical Engineering, 153, 107441",
        page_table="Membrane table (as reproduced in review Fig. 8)",
        verification_status="report-extracted",
    ),
    "ruizgarcia2019": dict(
        title="Different boron rejection behavior in two RO membranes installed in the same full-scale SWRO desalination plant",
        authors="Ruiz-García, A.; Leon, F.; Ramos-Martín, A.",
        year=2019,
        doi="10.1016/j.desal.2018.07.012",
        url="https://doi.org/10.1016/j.desal.2018.07.012",
        source_type="peer-reviewed",
        publisher="Desalination",
        page_table="Plant data (as reproduced in review Fig. 9)",
        verification_status="report-extracted",
    ),
    "conidi2018": dict(
        title="Performance of Reverse Osmosis Membranes in the Treatment of Flue-Gas Desulfurization (FGD) Wastewaters",
        authors="Conidi, C.; Macedonio, F.; Argurio, P.; Cassano, A.; Drioli, E.",
        year=2018,
        doi="10.3390/environments5060071",
        url="https://doi.org/10.3390/environments5060071",
        source_type="peer-reviewed",
        publisher="Environments",
        page_table="Membrane characteristics and results (as reproduced in review Figs. 8-9)",
        verification_status="report-extracted",
        notes="Special FGD-wastewater study; results must not be generalised to seawater or brackish ratings.",
    ),
    "gilabert2023": dict(
        title="Sustainability and cost of water savings through new high rejection FILMTEC BW30XHR PRO-440 membrane for seawater desalination",
        authors="Gilabert-Oriol, G.; Niewersch, C.; Alomar, H.; García-Molina, V.",
        year=2023,
        doi="10.5004/dwt.2023.29922",
        url="https://doi.org/10.5004/dwt.2023.29922",
        source_type="peer-reviewed",
        publisher="Desalination and Water Treatment",
        verification_status="report-extracted",
    ),
    "ansari2021": dict(
        title="Performance evaluation of a brackish water reverse osmosis pilot-plant desalination process under different operating conditions: Experimental study",
        authors="Ansari, M.; Al-Obaidi, M.; Hadadian, Z.; Haghighi, A.; Mujtaba, I.",
        year=2021,
        doi="10.1016/j.clet.2021.100134",
        url="https://doi.org/10.1016/j.clet.2021.100134",
        source_type="peer-reviewed",
        publisher="Cleaner Engineering and Technology, 4, 100134",
        verification_status="report-extracted",
    ),
    "alkatheeri2021": dict(
        title="Robust Spatial Modeling of Thermodynamic Parameters in a Full-Scale Reverse Osmosis Membrane Channel",
        authors="Alkatheeri, A.; Rafay, R.; Alhseinat, E.; Safieh, A.; Alnaimat, F.",
        year=2021,
        doi="10.1021/acsomega.0c04412",
        url="https://doi.org/10.1021/acsomega.0c04412",
        source_type="peer-reviewed",
        publisher="ACS Omega, 6, 12392-12409",
        verification_status="report-extracted",
    ),
    "ds_bw30_400_34i": dict(
        title="DOW FILMTEC BW30-400/34i Product Information (Form No. 609-00481-0910)",
        authors=None,
        year=2010,
        url="https://www.lenntech.com/data-sheets/Dow-Filmtec-BW30-400%2034i-L.pdf",
        source_type="manufacturer-datasheet",
        publisher="The Dow Chemical Company (copy hosted by Lenntech)",
        page_table="Product Specifications; Operating Limits (pp. 1-2)",
        verification_status="verified",
        notes=f"Text extracted and read {VERIFIED_ON}. Distributor-hosted copy of the manufacturer document.",
    ),
    "ds_sw30hr_380": dict(
        title="DOW FILMTEC SW30HR-380 Element Product Data Sheet (Form No. 609-00390, Rev. 0, December 2016)",
        year=2016,
        url="https://espwaterproducts.com/cdn/shop/files/FilmTec_SW30HR-380_Seawater_RO_Membrane_Spec_Sheet.pdf",
        source_type="manufacturer-datasheet",
        publisher="The Dow Chemical Company (copy hosted by ESP Water Products)",
        page_table="Product Specifications; Operating and Cleaning Limits (pp. 1-2)",
        verification_status="verified",
        notes=f"Text extracted and read {VERIFIED_ON}.",
    ),
    "ds_sw30xle_440": dict(
        title="FilmTec SW30XLE-440 Element Product Data Sheet (Form No. 45-D00966-en, Rev. 4, November 2019)",
        year=2019,
        url="https://www.lenntech.com/data-sheets/DuPont-FilmTec-SW30XLE-440-L.pdf",
        source_type="manufacturer-datasheet",
        publisher="DuPont Water Solutions (copy hosted by Lenntech)",
        page_table="Typical Properties; Operating and Cleaning Limits (p. 1)",
        verification_status="verified",
        notes=f"Text extracted and read {VERIFIED_ON}.",
    ),
    "ds_swc4plus": dict(
        title="Hydranautics Membrane Element SWC4+ specification sheet (dated 10/07/13)",
        year=2013,
        url="https://membranes.com/swc4",
        source_type="manufacturer-datasheet",
        publisher="Hydranautics (Nitto Group)",
        page_table="Performance; Application Data; Test Conditions",
        verification_status="verified",
        notes=f"Text extracted and read {VERIFIED_ON}. Stated performance is initial (after 30 min of operation).",
    ),
    "ds_espa_2540": dict(
        title="Hydranautics Membrane Element ESPA-2540 specification sheet (dated 2/25/15)",
        year=2015,
        url="https://membranes.com/espa-2540",
        source_type="manufacturer-datasheet",
        publisher="Hydranautics (Nitto Group)",
        page_table="Performance; Application Data; Test Conditions",
        verification_status="verified",
        notes=f"Text extracted and read {VERIFIED_ON}. Stated performance is initial (after 30 min of operation).",
    ),
}

R, V = "report-extracted", "verified"
MR = "manufacturer-rated"

# Helper to build spec dicts compactly.
def s(parameter, value, unit, source, verification, *, value_min=None, value_max=None, value_text=None,
      test_conditions=None, notes=None, evidence_type=MR):
    return dict(parameter=parameter, value=value, value_min=value_min, value_max=value_max, value_text=value_text,
                unit=unit, source=source, verification_status=verification, test_conditions=test_conditions,
                notes=notes, evidence_type=evidence_type)


BW30_TEST = "2,000 ppm NaCl, 225 psi (15.5 bar), 77 °F (25 °C), pH 8, 15% recovery"
SW30HR_TEST = "32,000 ppm NaCl, 800 psi (5.5 MPa), 77 °F (25 °C), pH 8, 8% recovery"
SW30XLE_TEST = "32,000 ppm NaCl, 5 ppm boron, 800 psi (5.5 MPa), 77 °F (25 °C), pH 8, 8% recovery"
SWC4_TEST = "32,000 ppm NaCl, 800 psi (5.5 MPa) applied pressure, 77 °F (25 °C), 10% permeate recovery, pH 6.5-7.0; initial data after 30 min"
ESPA_TEST = "1,500 ppm NaCl, 150 psi (1.03 MPa) applied pressure, 77 °F (25 °C), 10% permeate recovery, pH 6.5-7.0; initial data after 30 min"
KARAN_SW_TEST = "32,000 ppm NaCl, 55 bar (as tabulated by Karan & Livingston 2020)"
KARAN_BW_TEST = "2,000 ppm NaCl, 15.5 bar (as tabulated by Karan & Livingston 2020)"


def _datasheet_limits(src, pmax, pmax_text, dp, dp_text, feed_flow=None, feed_flow_text=None,
                         turbidity=None, sdi=5.0, ph=(2, 11), ph_clean=(1, 13)):
    specs = [
        s("max_operating_pressure_bar", pmax, "bar", src, V, value_text=pmax_text),
        s("max_operating_temperature_c", 45.0, "°C", src, V, value_text="113 °F (45 °C)"),
        s("ph_continuous_min", ph[0], "pH", src, V, value_text=f"pH range, continuous: {ph[0]}-{ph[1]}"),
        s("ph_continuous_max", ph[1], "pH", src, V, value_text=f"pH range, continuous: {ph[0]}-{ph[1]}"),
        s("ph_cleaning_min", ph_clean[0], "pH", src, V, value_text=f"short-term cleaning: {ph_clean[0]}-{ph_clean[1]}"),
        s("ph_cleaning_max", ph_clean[1], "pH", src, V, value_text=f"short-term cleaning: {ph_clean[0]}-{ph_clean[1]}"),
        s("max_free_chlorine_mg_l", 0.1, "mg/L", src, V, value_text="< 0.1 ppm",
          notes="Stated as less than 0.1 ppm. Oxidation damage is excluded from warranty; dechlorination upstream is expected."),
        s("max_feed_sdi", sdi, "SDI15", src, V, value_text=f"SDI {sdi:g}"),
        s("max_element_pressure_drop_bar", dp, "bar", src, V, value_text=dp_text),
    ]
    if turbidity is not None:
        specs.append(s("max_feed_turbidity_ntu", turbidity, "NTU", src, V, value_text=f"{turbidity} NTU"))
    if feed_flow is not None:
        specs.append(s("max_feed_flow_m3h", feed_flow, "m³/h", src, V, value_text=feed_flow_text))
    return specs


MEMBRANES: list[dict] = [
    dict(
        manufacturer="FilmTec (Dow/DuPont)", model="BW30-400", category="BWRO", intended_applications=["bwro"],
        element_size="8 in", verification_status=R,
        notes="Named in the review with pilot-plant data (Ansari et al., 2021). No datasheet for this exact model was "
              "verified; the verified BW30-400/34i datasheet is stored under its own record and not transferred here.",
        specs=[],
        observations=[
            dict(evidence_type="pilot-plant", feed_description="Brackish feed, varying salinity",
                 feed_salinity_text="1,000-5,000 ppm", pressure_bar=13.0, pressure_text="5-13 bar (13 bar point)",
                 recovery_text="Not reported", salt_rejection_pct=98.8,
                 performance_text="13 bar gave 98.8% rejection", permeate_concentration_text="12 ppm minimum at 13 bar",
                 test_method="Pilot plant", source="ansari2021", verification_status=R),
            dict(evidence_type="pilot-plant", feed_description="Brackish feed, varying salinity",
                 feed_salinity_text="1,000-5,000 ppm", pressure_text="5 → 13 bar", recovery_text="Not reported",
                 performance_text="Permeate salinity fell 73.3% as pressure increased from 5 to 13 bar",
                 permeate_concentration_text="Not directly stated per point", test_method="Pilot plant",
                 source="ansari2021", verification_status=R),
        ],
    ),
    dict(
        manufacturer="FilmTec (Dow/DuPont)", model="BW30-400/34i", category="BWRO", intended_applications=["bwro"],
        element_size="8 x 40 in (34 mil feed spacer)", verification_status=V,
        feed_limitations="Datasheet: maximum feed SDI 5; free chlorine < 0.1 ppm; maximum temperature for continuous operation above pH 10 is 35 °C.",
        notes="Datasheet describes this element for high-fouling or challenging brackish feeds. It does not name "
              "industrial wastewater or reuse service, so that application is not claimed.",
        specs=[
            s("active_area_m2", 37.0, "m²", "ds_bw30_400_34i", V, value_text="400 ft² (37 m²)", notes="Active area guaranteed ±5%."),
            s("rated_permeate_flow_m3d", 40.0, "m³/d", "ds_bw30_400_34i", V, value_text="10,500 gpd (40 m³/d)",
              test_conditions=BW30_TEST, notes="Individual elements may be up to 15% below this value."),
            s("rated_salt_rejection_pct", 99.5, "%", "ds_bw30_400_34i", V, value_text="Stabilized salt rejection 99.5%", test_conditions=BW30_TEST),
            s("min_salt_rejection_pct", 99.0, "%", "ds_bw30_400_34i", V, value_text="Minimum salt rejection 99.0%", test_conditions=BW30_TEST),
            s("test_nacl_mg_l", 2000.0, "mg/L", "ds_bw30_400_34i", V, test_conditions=BW30_TEST),
            s("test_pressure_bar", 15.5, "bar", "ds_bw30_400_34i", V, value_text="225 psi (15.5 bar)", test_conditions=BW30_TEST),
            s("test_temperature_c", 25.0, "°C", "ds_bw30_400_34i", V, test_conditions=BW30_TEST),
            s("test_recovery_pct", 15.0, "%", "ds_bw30_400_34i", V, test_conditions=BW30_TEST),
            s("test_ph", 8.0, "pH", "ds_bw30_400_34i", V, test_conditions=BW30_TEST),
        ] + _datasheet_limits("ds_bw30_400_34i", 41.0, "600 psig (41 bar)", 1.0, "15 psig (1.0 bar)",
                                 feed_flow=19.0, feed_flow_text="85 gpm (19 m³/hr)"),
    ),
    dict(
        manufacturer="FilmTec (Dow/DuPont)", model="BW30LE-440", category="BWRO-low-energy", intended_applications=["bwro"],
        element_size="8 in", verification_status=R,
        notes="Named in the review as a documented model; no specification values were reported there and no datasheet was verified.",
        specs=[], observations=[],
    ),
    dict(
        manufacturer="FilmTec (Dow/DuPont)", model="SW30-HR", category="SWRO", intended_applications=["swro"],
        verification_status=R,
        notes="Model named without size suffix in Karan & Livingston (2020). Not assumed identical to SW30HR-380, "
              "whose verified datasheet is stored separately (values differ: 99.82% vs 99.7% rejection).",
        specs=[
            s("rated_flux_lmh", 25.4, "LMH", "karan2020", R, test_conditions=KARAN_SW_TEST),
            s("rated_salt_rejection_pct", 99.82, "%", "karan2020", R, test_conditions=KARAN_SW_TEST),
            s("test_nacl_mg_l", 32000.0, "mg/L", "karan2020", R, test_conditions=KARAN_SW_TEST),
            s("test_pressure_bar", 55.0, "bar", "karan2020", R, test_conditions=KARAN_SW_TEST),
        ],
    ),
    dict(
        manufacturer="FilmTec (Dow/DuPont)", model="SW30HR-380", category="SWRO", intended_applications=["swro"],
        element_size="8 x 40 in", verification_status=V,
        feed_limitations="Datasheet: maximum feed SDI 5; free chlorine < 0.1 ppm.",
        notes="Datasheet footnote: operation up to 1,000 psig (69 bar) is allowable under certain conditions; consult manufacturer above 1,000 psig and/or above 35 °C.",
        specs=[
            s("active_area_m2", 35.0, "m²", "ds_sw30hr_380", V, value_text="380 ft² (35 m²)"),
            s("rated_permeate_flow_m3d", 24.6, "m³/d", "ds_sw30hr_380", V, value_text="6,500 GPD (24.6 m³/d)",
              test_conditions=SW30HR_TEST, notes="Individual elements may vary ±15%."),
            s("rated_salt_rejection_pct", 99.7, "%", "ds_sw30hr_380", V, value_text="Typical stabilized salt rejection 99.7%", test_conditions=SW30HR_TEST),
            s("min_salt_rejection_pct", 99.65, "%", "ds_sw30hr_380", V, test_conditions=SW30HR_TEST),
            s("test_nacl_mg_l", 32000.0, "mg/L", "ds_sw30hr_380", V, test_conditions=SW30HR_TEST),
            s("test_pressure_bar", 55.0, "bar", "ds_sw30hr_380", V, value_text="800 psi (5.5 MPa)", test_conditions=SW30HR_TEST),
            s("test_temperature_c", 25.0, "°C", "ds_sw30hr_380", V, test_conditions=SW30HR_TEST),
            s("test_recovery_pct", 8.0, "%", "ds_sw30hr_380", V, test_conditions=SW30HR_TEST),
            s("test_ph", 8.0, "pH", "ds_sw30hr_380", V, test_conditions=SW30HR_TEST),
        ] + _datasheet_limits("ds_sw30hr_380", 68.9, "1,000 psig (69 bar)", 1.0, "15 psig (1.0 bar)"),
    ),
    dict(
        manufacturer="FilmTec (Dow/DuPont)", model="SW30-XLE", category="SWRO-low-energy", intended_applications=["swro"],
        verification_status=R,
        notes="Model named without size suffix in Karan & Livingston (2020); not assumed identical to SW30XLE-440.",
        specs=[
            s("rated_flux_lmh", 38.0, "LMH", "karan2020", R, test_conditions=KARAN_SW_TEST),
            s("rated_salt_rejection_pct", 99.8, "%", "karan2020", R, test_conditions=KARAN_SW_TEST),
            s("test_nacl_mg_l", 32000.0, "mg/L", "karan2020", R, test_conditions=KARAN_SW_TEST),
            s("test_pressure_bar", 55.0, "bar", "karan2020", R, test_conditions=KARAN_SW_TEST),
        ],
    ),
    dict(
        manufacturer="FilmTec (DuPont)", model="SW30XLE-440", category="SWRO-low-energy", intended_applications=["swro", "bwro"],
        element_size="8 x 40 in", verification_status=V,
        feed_limitations="Datasheet: intended for medium-salinity, medium-temperature seawater; also two-pass seawater or high-salinity brackish designs. Max SDI 5; free chlorine < 0.1 ppm.",
        specs=[
            s("active_area_m2", 41.0, "m²", "ds_sw30xle_440", V, value_text="440 ft² (41 m²)", notes="Active area guaranteed ±5%."),
            s("rated_permeate_flow_m3d", 37.4, "m³/d", "ds_sw30xle_440", V, value_text="9,900 gpd (37.4 m³/d)",
              test_conditions=SW30XLE_TEST, notes="Individual elements may vary ±15%."),
            s("rated_salt_rejection_pct", 99.8, "%", "ds_sw30xle_440", V, value_text="Stabilized salt rejection 99.8%", test_conditions=SW30XLE_TEST),
            s("min_salt_rejection_pct", 99.6, "%", "ds_sw30xle_440", V, test_conditions=SW30XLE_TEST),
            s("boron_rejection_pct", 91.5, "%", "ds_sw30xle_440", V, value_text="Stabilized boron rejection 91.5%", test_conditions=SW30XLE_TEST),
            s("test_nacl_mg_l", 32000.0, "mg/L", "ds_sw30xle_440", V, test_conditions=SW30XLE_TEST),
            s("test_pressure_bar", 55.0, "bar", "ds_sw30xle_440", V, value_text="800 psi (5.5 MPa)", test_conditions=SW30XLE_TEST),
            s("test_temperature_c", 25.0, "°C", "ds_sw30xle_440", V, test_conditions=SW30XLE_TEST),
            s("test_recovery_pct", 8.0, "%", "ds_sw30xle_440", V, test_conditions=SW30XLE_TEST),
            s("test_ph", 8.0, "pH", "ds_sw30xle_440", V, test_conditions=SW30XLE_TEST),
        ] + _datasheet_limits("ds_sw30xle_440", 82.7, "1,200 psig (83 bar)", 1.0, "15 psig (1.0 bar)"),
    ),
    dict(
        manufacturer="FilmTec (Dow/DuPont)", model="SW30XFR-400/34", category="SWRO", intended_applications=["swro"],
        verification_status=R, notes="Named in the review; no values reported there and no datasheet verified.", specs=[],
    ),
    dict(
        manufacturer="FilmTec (Dow/DuPont)", model="BW30XFR", category="BWRO-fouling-resistant", intended_applications=["bwro"],
        verification_status=R, notes="Named in the review with a laboratory model-validation study only; no rated values available.",
        specs=[],
        observations=[
            dict(evidence_type="laboratory-experimental", feed_description="NaCl solution", feed_salinity_mg_l=10000.0,
                 feed_salinity_text="10 g/L NaCl", pressure_bar=29.0, temperature_c=25.0,
                 recovery_text="Stepped to high recovery",
                 performance_text="Spatial model error within 5% for salinity and flux", permeate_concentration_text="Not reported",
                 test_method="Lab validation", source="alkatheeri2021", verification_status=R),
        ],
    ),
    dict(
        manufacturer="FilmTec (DuPont)", model="SW30ULE-440i", category="SWRO-low-energy", intended_applications=["swro"],
        verification_status=R, notes="Named in the review; no values reported there and no datasheet verified.", specs=[],
    ),
    dict(
        manufacturer="FilmTec (DuPont)", model="BW30XHR PRO-440", category="BWRO-high-rejection",
        intended_applications=["second_pass", "industrial"], verification_status=R,
        notes="Reported in the review as a high-rejection BWRO / second-pass element (Gilabert-Oriol et al., 2023).",
        specs=[],
        observations=[
            dict(evidence_type="laboratory-experimental", feed_description="Synthetic solutions at standard test conditions",
                 salt_rejection_pct=99.8, performance_text="99.8% rejection for Na and Cl",
                 test_method="Experimental, manufacturer-referenced standard test conditions", source="gilabert2023",
                 verification_status=R, notes="Exact test salinity/pressure not reproduced in the review."),
        ],
    ),
    dict(
        manufacturer="Hydranautics (Nitto)", model="ESPA-2540", category="BWRO-low-energy", intended_applications=["bwro"],
        element_size="2.5 x 40 in", verification_status=V,
        feed_limitations="Datasheet: max turbidity 1.0 NTU; max SDI 4.0; free chlorine < 0.1 ppm; minimum concentrate-to-permeate ratio 5:1 per element.",
        notes="Small 2.5-inch element: element counts for large flows will be high. FGD-wastewater results (Conidi 2018) are a special case.",
        specs=[
            s("active_area_m2", 2.37, "m²", "ds_espa_2540", V, value_text="25.5 ft²", notes="Converted from 25.5 ft²."),
            s("rated_permeate_flow_m3d", 2.84, "m³/d", "ds_espa_2540", V, value_text="750 gpd (2.84 m³/d)", test_conditions=ESPA_TEST,
              notes="Minimum permeate flow for individual elements is 15% below listed flow."),
            s("rated_salt_rejection_pct", 99.4, "%", "ds_espa_2540", V, value_text="99.4% (98.0% minimum)", test_conditions=ESPA_TEST),
            s("min_salt_rejection_pct", 98.0, "%", "ds_espa_2540", V, test_conditions=ESPA_TEST),
            s("test_nacl_mg_l", 1500.0, "mg/L", "ds_espa_2540", V, test_conditions=ESPA_TEST),
            s("test_pressure_bar", 10.3, "bar", "ds_espa_2540", V, value_text="150 psi (1.03 MPa)", test_conditions=ESPA_TEST),
            s("test_temperature_c", 25.0, "°C", "ds_espa_2540", V, test_conditions=ESPA_TEST),
            s("test_recovery_pct", 10.0, "%", "ds_espa_2540", V, test_conditions=ESPA_TEST),
            s("test_ph", None, "pH", "ds_espa_2540", V, value_min=6.5, value_max=7.0, value_text="6.5-7.0", test_conditions=ESPA_TEST),
        ] + _datasheet_limits("ds_espa_2540", 20.7, "300 psig (2.1 MPa)", 0.69, "10 psi", feed_flow=1.36,
                                 feed_flow_text="6 GPM (23 l/m)", turbidity=1.0, sdi=4.0, ph=(2, 10), ph_clean=(1, 12))
        + [s("min_concentrate_permeate_ratio", 5.0, "ratio", "ds_espa_2540", V,
             value_text="Minimum Ratio of Concentrate to Permeate Flow for any element: 5:1")],
        observations=[
            dict(evidence_type="laboratory-experimental", feed_description="Softened FGD wastewater",
                 pressure_bar=18.0, temperature_c=20.0, recovery_text="Up to 50% recovery factor",
                 performance_text="Na rejection about 80%; Ca/Mg > 86.5%", permeate_concentration_text="Not reported",
                 test_method="Lab spiral-wound", source="conidi2018", verification_status=R,
                 notes="Special wastewater experiment; not a general rating."),
        ],
    ),
    dict(
        manufacturer="Hydranautics (Nitto)", model="SWC-2540", category="SWRO", intended_applications=["swro"],
        element_size="2.5 in", verification_status=R,
        notes="The review reports '99.4% minimum; 99%' with conditions '20 °C, 26 bar, 204 L/h' from an FGD-wastewater study; "
              "the test salinity is not reported, so the value cannot be used for performance estimation.",
        specs=[
            s("min_salt_rejection_pct", 99.4, "%", "conidi2018", R, value_text="99.4% minimum; 99%",
              test_conditions="20 °C, 26 bar, 204 L/h (feed salinity not reported in review)",
              notes="Ambiguous as reproduced in the review; verify against the original paper and datasheet."),
        ],
        observations=[
            dict(evidence_type="laboratory-experimental", feed_description="Softened FGD wastewater",
                 pressure_text="16-50 bar", temperature_c=20.0, recovery_text="Up to 50% recovery factor",
                 performance_text="Na rejection about 95.5%; Mg completely rejected", permeate_concentration_text="Not reported",
                 test_method="Lab spiral-wound", source="conidi2018", verification_status=R,
                 notes="Special wastewater experiment; not a general seawater rating."),
        ],
    ),
    dict(
        manufacturer="Hydranautics (Nitto)", model="SWC4+", category="SWRO", intended_applications=["swro"],
        element_size="8 x 40 in", verification_status=V,
        feed_limitations="Datasheet: max turbidity 1.0 NTU; max SDI 5.0; free chlorine < 0.1 ppm; minimum concentrate-to-permeate ratio 5:1 per element.",
        specs=[
            s("active_area_m2", 37.1, "m²", "ds_swc4plus", V, value_text="400 ft² (37.1 m²)", notes="Active area may vary ±4%."),
            s("rated_permeate_flow_m3d", 24.6, "m³/d", "ds_swc4plus", V, value_text="6,500 gpd (24.6 m³/d)", test_conditions=SWC4_TEST,
              notes="Individual elements may vary ±15%."),
            s("rated_salt_rejection_pct", 99.8, "%", "ds_swc4plus", V, value_text="99.8% (99.7% minimum)", test_conditions=SWC4_TEST),
            s("min_salt_rejection_pct", 99.7, "%", "ds_swc4plus", V, test_conditions=SWC4_TEST),
            s("boron_rejection_pct", 93.0, "%", "ds_swc4plus", V, value_text="Boron rejection (typical) 93.0%",
              test_conditions=SWC4_TEST + "; 5.0 ppm boron in feed"),
            s("test_nacl_mg_l", 32000.0, "mg/L", "ds_swc4plus", V, test_conditions=SWC4_TEST),
            s("test_pressure_bar", 55.0, "bar", "ds_swc4plus", V, value_text="800 psi (5.5 MPa)", test_conditions=SWC4_TEST),
            s("test_temperature_c", 25.0, "°C", "ds_swc4plus", V, test_conditions=SWC4_TEST),
            s("test_recovery_pct", 10.0, "%", "ds_swc4plus", V, test_conditions=SWC4_TEST),
            s("test_ph", None, "pH", "ds_swc4plus", V, value_min=6.5, value_max=7.0, value_text="6.5-7.0", test_conditions=SWC4_TEST),
        ] + _datasheet_limits("ds_swc4plus", 82.7, "1200 psig (8.27 MPa)", 0.69, "10 psi", feed_flow=17.0,
                                 feed_flow_text="75 GPM (17.0 m³/h)", turbidity=1.0)
        + [s("min_concentrate_permeate_ratio", 5.0, "ratio", "ds_swc4plus", V,
             value_text="Minimum Ratio of Concentrate to Permeate Flow for any Element: 5:1")],
    ),
    dict(
        manufacturer="Toray", model="TM820L-440", category="SWRO", intended_applications=["swro"],
        verification_status=R, notes="Review lists area only; rated flow/rejection not reported; datasheet not verified.",
        specs=[
            s("active_area_m2", 40.88, "m²", "ruizgarcia2021", R, test_conditions="Manufacturer test conditions referenced (not reproduced)",
              notes="Review classes this as manufacturer-rated / simulated."),
        ],
        observations=[
            dict(evidence_type="pilot-plant", feed_description="Full-scale SWRO plant", feed_salinity_text="Variable",
                 pressure_text="Variable", recovery_text="Variable",
                 performance_text="Lower boron permeate than TM820S-400 installed in the same plant",
                 permeate_concentration_text="0.25-0.75 mg/L boron", test_method="Full-scale plant data",
                 source="ruizgarcia2019", verification_status=R),
        ],
    ),
    dict(
        manufacturer="Toray", model="TM820S-400", category="SWRO", intended_applications=["swro"],
        verification_status=R, notes="Review lists area only; rated flow/rejection not reported; datasheet not verified.",
        specs=[
            s("active_area_m2", 37.16, "m²", "ruizgarcia2021", R, test_conditions="Manufacturer test conditions referenced (not reproduced)"),
        ],
        observations=[
            dict(evidence_type="pilot-plant", feed_description="Full-scale SWRO plant", feed_salinity_text="Variable",
                 pressure_text="Variable", recovery_text="Variable", performance_text="Boron permeate 0.5-2 mg/L",
                 permeate_concentration_text="0.5-2 mg/L boron", test_method="Full-scale plant data",
                 source="ruizgarcia2019", verification_status=R),
        ],
    ),
    dict(
        manufacturer="Toray", model="TM820V-400", category="SWRO", intended_applications=["swro"],
        verification_status=R, notes="Named in the review; no values reported there and no datasheet verified.", specs=[],
    ),
    dict(
        manufacturer="Toray", model="TM82V", category="SWRO", intended_applications=["swro"], verification_status=R,
        notes="Karan & Livingston (2020) table; test conditions not reported, so values cannot be normalised.",
        specs=[
            s("rated_flux_lmh", 45.8, "LMH", "karan2020", R, test_conditions="Not reported"),
            s("rated_salt_rejection_pct", 99.7, "%", "karan2020", R, test_conditions="Not reported"),
        ],
    ),
    dict(
        manufacturer="LG Chem", model="SW 400 R", category="SWRO", intended_applications=["swro"], verification_status=R,
        notes="Values from Mostafaa et al. (2021) system-specification table as reproduced in the review; test conditions "
              "and operating limits not reported there. Manufacturer datasheet not yet verified.",
        specs=[
            s("active_area_m2", 37.0, "m²", "mostafaa2021", R, test_conditions="Tabled system specs"),
            s("rated_permeate_flow_m3d", 34.1, "m³/d", "mostafaa2021", R, test_conditions="Tabled system specs (test conditions not reported)"),
            s("rated_salt_rejection_pct", 99.85, "%", "mostafaa2021", R, value_text="Stabilized 99.85%", test_conditions="Tabled system specs"),
            s("min_salt_rejection_pct", 99.7, "%", "mostafaa2021", R, test_conditions="Tabled system specs"),
            s("boron_rejection_pct", 93.0, "%", "mostafaa2021", R, test_conditions="Tabled system specs"),
        ],
    ),
    dict(
        manufacturer="Trisep (Microdyn-Nadir)", model="X-201", category="Industrial", intended_applications=["industrial"],
        verification_status=R, notes="Karan & Livingston (2020) table lists this as an industrial/wastewater element.",
        specs=[
            s("rated_flux_lmh", 43.4, "LMH", "karan2020", R, test_conditions=KARAN_BW_TEST),
            s("rated_salt_rejection_pct", None, "%", "karan2020", R, value_min=99.0, value_max=99.5, value_text="99.0-99.5%",
              test_conditions=KARAN_BW_TEST),
            s("test_nacl_mg_l", 2000.0, "mg/L", "karan2020", R, test_conditions=KARAN_BW_TEST),
            s("test_pressure_bar", 15.5, "bar", "karan2020", R, test_conditions=KARAN_BW_TEST),
        ],
    ),
]
