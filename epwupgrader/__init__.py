"""Morph EnergyPlus EPW weather files to future climates."""

__version__ = "0.2.0"

from epwupgrader.morphing import (  # noqa: E402
    apply_all_morphing,
    morph_radiation,
    morph_temperature,
    morph_wind_speed,
)
from epwupgrader.parser import detect_baseline_year, parse_epw, parse_epw_meta  # noqa: E402
from epwupgrader.psychrometrics import (  # noqa: E402
    recalculate_dew_point_after_temp_shift,
    recalculate_rh_after_temp_shift,
    saturation_vapour_pressure,
    scale_rh_for_temp_shift,
)
from epwupgrader.scenarios import (  # noqa: E402
    get_monthly_anomalies,
    load_anomalies_csv,
    to_coefficients,
)
from epwupgrader.writer import annotate_header, write_epw  # noqa: E402

__all__ = [
    "__version__",
    "annotate_header",
    "apply_all_morphing",
    "detect_baseline_year",
    "get_monthly_anomalies",
    "load_anomalies_csv",
    "morph_radiation",
    "morph_temperature",
    "morph_wind_speed",
    "parse_epw",
    "parse_epw_meta",
    "recalculate_dew_point_after_temp_shift",
    "recalculate_rh_after_temp_shift",
    "saturation_vapour_pressure",
    "scale_rh_for_temp_shift",
    "to_coefficients",
    "write_epw",
]
