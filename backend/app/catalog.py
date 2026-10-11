"""Canonical specification parameters and their units."""

PARAMETERS: dict[str, tuple[str, str]] = {
    "active_area_m2": ("Active membrane area", "m²"),
    "rated_permeate_flow_m3d": ("Rated permeate flow", "m³/d"),
    "rated_flux_lmh": ("Rated flux", "LMH"),
    "rated_salt_rejection_pct": ("Rated (stabilized/nominal) salt rejection", "%"),
    "min_salt_rejection_pct": ("Minimum salt rejection", "%"),
    "boron_rejection_pct": ("Boron rejection", "%"),
    "test_nacl_mg_l": ("Test salinity (NaCl)", "mg/L"),
    "test_pressure_bar": ("Test pressure", "bar"),
    "test_temperature_c": ("Test temperature", "°C"),
    "test_recovery_pct": ("Test recovery", "%"),
    "test_ph": ("Test pH", "pH"),
    "max_operating_pressure_bar": ("Maximum operating pressure", "bar"),
    "max_operating_temperature_c": ("Maximum operating temperature", "°C"),
    "ph_continuous_min": ("pH continuous, minimum", "pH"),
    "ph_continuous_max": ("pH continuous, maximum", "pH"),
    "ph_cleaning_min": ("pH cleaning, minimum", "pH"),
    "ph_cleaning_max": ("pH cleaning, maximum", "pH"),
    "max_free_chlorine_mg_l": ("Free chlorine tolerance", "mg/L"),
    "max_feed_sdi": ("Maximum feed SDI", "SDI15"),
    "max_feed_turbidity_ntu": ("Maximum feed turbidity", "NTU"),
    "max_element_pressure_drop_bar": ("Maximum element pressure drop", "bar"),
    "max_feed_flow_m3h": ("Maximum feed flow per element", "m³/h"),
    "min_concentrate_permeate_ratio": ("Minimum concentrate-to-permeate flow ratio per element", "ratio"),
}

# Parameters that the engine needs to move a candidate beyond "insufficient evidence"
CRITICAL_PARAMETERS = [
    "max_operating_pressure_bar",
    "max_operating_temperature_c",
    "rated_salt_rejection_pct",
    "test_nacl_mg_l",
    "test_pressure_bar",
]
PERFORMANCE_PARAMETERS = ["rated_permeate_flow_m3d", "active_area_m2", "rated_flux_lmh"]
