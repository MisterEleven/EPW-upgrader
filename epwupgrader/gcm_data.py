"""
gcm_data.py
-----------
Mock CMIP6 / SSP5-8.5 monthly anomaly data for the EPW morphing pipeline.

The SSP585_2050 dictionary stores reference anomaly values anchored to
year 2100 (end-of-century).  The get_monthly_anomalies() function
interpolates these linearly to any target year between baseline_year
and 2100, which is the standard approach used by pyepwmorph and similar
tools.

Data source (mock): Representative values consistent with the CMIP6
SSP5-8.5 multi-model ensemble median as reported in IPCC AR6 WGI
Chapter 4 (2021).  Replace with real netCDF4 / xarray ingestion for
production use.
"""

from __future__ import annotations
from typing import Dict

# ---------------------------------------------------------------------------
# Raw end-of-century (2100) reference anomaly tables
# Keys: month integer 1-12
# delta_temp_c            : additive dry-bulb temperature shift [degC]
# alpha_solar             : multiplicative scaling factor for GHI/DNI/DHI
# beta_wind               : multiplicative scaling factor for wind speed
# tail_amplification_factor: extra multiplier applied to hours above the
#                            monthly 99th-percentile baseline temperature
# ---------------------------------------------------------------------------

SSP585_2050: Dict[int, Dict[str, float]] = {
    1:  {"delta_temp_c": 4.2,  "alpha_solar": 1.02, "beta_wind": 0.97, "tail_amplification_factor": 1.5},
    2:  {"delta_temp_c": 4.1,  "alpha_solar": 1.02, "beta_wind": 0.97, "tail_amplification_factor": 1.5},
    3:  {"delta_temp_c": 3.9,  "alpha_solar": 1.03, "beta_wind": 0.98, "tail_amplification_factor": 1.5},
    4:  {"delta_temp_c": 3.7,  "alpha_solar": 1.03, "beta_wind": 0.98, "tail_amplification_factor": 1.5},
    5:  {"delta_temp_c": 3.6,  "alpha_solar": 1.04, "beta_wind": 0.99, "tail_amplification_factor": 1.5},
    6:  {"delta_temp_c": 3.8,  "alpha_solar": 1.05, "beta_wind": 0.99, "tail_amplification_factor": 1.5},
    7:  {"delta_temp_c": 4.0,  "alpha_solar": 1.05, "beta_wind": 0.98, "tail_amplification_factor": 1.5},
    8:  {"delta_temp_c": 4.1,  "alpha_solar": 1.04, "beta_wind": 0.98, "tail_amplification_factor": 1.5},
    9:  {"delta_temp_c": 3.9,  "alpha_solar": 1.03, "beta_wind": 0.98, "tail_amplification_factor": 1.5},
    10: {"delta_temp_c": 3.7,  "alpha_solar": 1.02, "beta_wind": 0.97, "tail_amplification_factor": 1.5},
    11: {"delta_temp_c": 3.9,  "alpha_solar": 1.02, "beta_wind": 0.97, "tail_amplification_factor": 1.5},
    12: {"delta_temp_c": 4.1,  "alpha_solar": 1.02, "beta_wind": 0.97, "tail_amplification_factor": 1.5},
}

SSP245_2100: Dict[int, Dict[str, float]] = {
    1:  {"delta_temp_c": 2.4,  "alpha_solar": 1.01, "beta_wind": 0.98, "tail_amplification_factor": 1.2},
    2:  {"delta_temp_c": 2.3,  "alpha_solar": 1.01, "beta_wind": 0.98, "tail_amplification_factor": 1.2},
    3:  {"delta_temp_c": 2.2,  "alpha_solar": 1.02, "beta_wind": 0.99, "tail_amplification_factor": 1.2},
    4:  {"delta_temp_c": 2.1,  "alpha_solar": 1.02, "beta_wind": 0.99, "tail_amplification_factor": 1.2},
    5:  {"delta_temp_c": 2.0,  "alpha_solar": 1.02, "beta_wind": 0.99, "tail_amplification_factor": 1.2},
    6:  {"delta_temp_c": 2.1,  "alpha_solar": 1.03, "beta_wind": 0.99, "tail_amplification_factor": 1.2},
    7:  {"delta_temp_c": 2.2,  "alpha_solar": 1.03, "beta_wind": 0.99, "tail_amplification_factor": 1.2},
    8:  {"delta_temp_c": 2.3,  "alpha_solar": 1.02, "beta_wind": 0.99, "tail_amplification_factor": 1.2},
    9:  {"delta_temp_c": 2.2,  "alpha_solar": 1.02, "beta_wind": 0.98, "tail_amplification_factor": 1.2},
    10: {"delta_temp_c": 2.1,  "alpha_solar": 1.01, "beta_wind": 0.98, "tail_amplification_factor": 1.2},
    11: {"delta_temp_c": 2.2,  "alpha_solar": 1.01, "beta_wind": 0.98, "tail_amplification_factor": 1.2},
    12: {"delta_temp_c": 2.3,  "alpha_solar": 1.01, "beta_wind": 0.98, "tail_amplification_factor": 1.2},
}

# Scenario name normalisation map
_SCENARIO_MAP = {
    "ssp585":   SSP585_2050,
    "ssp5-8.5": SSP585_2050,
    "rcp8.5":   SSP585_2050,
    "rcp85":    SSP585_2050,
    "ssp245":   SSP245_2100,
    "ssp2-4.5": SSP245_2100,
    "rcp4.5":   SSP245_2100,
    "rcp45":    SSP245_2100,
}


def get_monthly_anomalies(
    scenario: str = "SSP5-8.5",
    target_year: int = 2050,
    baseline_year: int = 1980,
) -> Dict[int, Dict[str, float]]:
    """
    Return a dict of monthly anomalies interpolated to *target_year*.

    Parameters
    ----------
    scenario : str
        Climate scenario string.  Accepted values (case-insensitive):
        ``"SSP5-8.5"``, ``"SSP585"``, ``"RCP8.5"``,
        ``"SSP2-4.5"``, ``"SSP245"``, ``"RCP4.5"``.
    target_year : int
        The future year to morph to.  Must be in [baseline_year, 2100].
    baseline_year : int
        The reference year of the baseline EPW data.  Defaults to 1980.

    Returns
    -------
    Dict[int, Dict[str, float]]
        Keys are month integers 1-12.  Each value is a dict with keys:
        ``delta_temp_c``, ``alpha_solar``, ``beta_wind``,
        ``tail_amplification_factor``.

    Notes
    -----
    Linear interpolation formula used for temperature shift::

        scale = (target_year - baseline_year) / (2100 - baseline_year)
        delta_temp_applied = delta_temp_2100 * scale

    For multiplicative factors (alpha_solar, beta_wind) we interpolate
    the *deviation from unity* so that the midpoint year always yields
    a physically meaningful intermediate value::

        alpha_applied = 1.0 + (alpha_2100 - 1.0) * scale
    """
    key = scenario.lower().replace(" ", "")
    if key not in _SCENARIO_MAP:
        raise ValueError(
            f"Unknown scenario '{scenario}'. "
            f"Choose from: {sorted(_SCENARIO_MAP.keys())}"
        )

    reference_table = _SCENARIO_MAP[key]

    if not (baseline_year <= target_year <= 2100):
        raise ValueError(
            f"target_year {target_year} is outside the valid range "
            f"[{baseline_year}, 2100]."
        )

    # Linear scale factor: 0.0 at baseline_year, 1.0 at 2100
    scale = (target_year - baseline_year) / (2100 - baseline_year)

    result: Dict[int, Dict[str, float]] = {}
    for month in range(1, 13):
        ref = reference_table[month]

        # Additive fields: scale directly
        delta_temp = ref["delta_temp_c"] * scale

        # Multiplicative fields: interpolate the deviation from 1.0
        alpha_solar = 1.0 + (ref["alpha_solar"] - 1.0) * scale
        beta_wind   = 1.0 + (ref["beta_wind"]   - 1.0) * scale

        # tail_amplification_factor is treated as a fixed property of the
        # scenario (it does not itself change with year)
        tail = ref["tail_amplification_factor"]

        result[month] = {
            "delta_temp_c":              round(delta_temp,  4),
            "alpha_solar":               round(alpha_solar, 6),
            "beta_wind":                 round(beta_wind,   6),
            "tail_amplification_factor": tail,
        }

    return result