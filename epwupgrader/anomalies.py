"""Anomaly detection and climate scenario utilities for EPW weather data.

This module provides:
  - Statistical z-score anomaly flagging (``flag_anomalies``)
  - Physical-bounds checking (``check_physical_bounds``)
  - Wind-specific anomaly detection (``detect_wind_anomalies``)
  - Anomaly count summary (``summarise_anomalies``)
  - GCM climate scenario data and interpolation (``get_monthly_anomalies``)
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default physical bounds for common EPW columns
# ---------------------------------------------------------------------------
_DEFAULT_BOUNDS: Dict[str, Tuple[float, float]] = {
    "dry_bulb_temperature":    (-70.0, 60.0),
    "dew_point_temperature":   (-70.0, 40.0),
    "relative_humidity":       (0.0, 100.0),
    "atmospheric_pressure":    (80000.0, 110000.0),
    "wind_speed":              (0.0, 100.0),
    "wind_direction":          (0.0, 360.0),
    "global_horiz_radiation":  (0.0, 1400.0),
    "direct_normal_radiation": (0.0, 1400.0),
    "diffuse_horiz_radiation": (0.0, 800.0),
}

# ---------------------------------------------------------------------------
# GCM end-of-century (2100) reference anomaly tables
# ---------------------------------------------------------------------------
_ANOMALIES_2100: Dict[str, Dict[int, Dict[str, float]]] = {
    "SSP5-8.5": {
        1:  {"delta_temp_c": 5.8, "alpha_solar": 0.97, "beta_wind": 0.96,
             "tail_amplification_factor": 1.5},
        2:  {"delta_temp_c": 5.6, "alpha_solar": 0.97, "beta_wind": 0.96,
             "tail_amplification_factor": 1.5},
        3:  {"delta_temp_c": 5.3, "alpha_solar": 0.99, "beta_wind": 0.97,
             "tail_amplification_factor": 1.5},
        4:  {"delta_temp_c": 5.0, "alpha_solar": 1.01, "beta_wind": 0.98,
             "tail_amplification_factor": 1.5},
        5:  {"delta_temp_c": 4.8, "alpha_solar": 1.03, "beta_wind": 0.99,
             "tail_amplification_factor": 1.5},
        6:  {"delta_temp_c": 4.9, "alpha_solar": 1.05, "beta_wind": 1.00,
             "tail_amplification_factor": 1.5},
        7:  {"delta_temp_c": 5.2, "alpha_solar": 1.06, "beta_wind": 1.01,
             "tail_amplification_factor": 1.5},
        8:  {"delta_temp_c": 5.4, "alpha_solar": 1.06, "beta_wind": 1.01,
             "tail_amplification_factor": 1.5},
        9:  {"delta_temp_c": 5.1, "alpha_solar": 1.03, "beta_wind": 1.00,
             "tail_amplification_factor": 1.5},
        10: {"delta_temp_c": 4.9, "alpha_solar": 1.00, "beta_wind": 0.99,
             "tail_amplification_factor": 1.5},
        11: {"delta_temp_c": 5.3, "alpha_solar": 0.98, "beta_wind": 0.97,
             "tail_amplification_factor": 1.5},
        12: {"delta_temp_c": 5.7, "alpha_solar": 0.97, "beta_wind": 0.96,
             "tail_amplification_factor": 1.5},
    },
    "SSP2-4.5": {
        1:  {"delta_temp_c": 2.8, "alpha_solar": 0.98, "beta_wind": 0.97,
             "tail_amplification_factor": 1.4},
        2:  {"delta_temp_c": 2.7, "alpha_solar": 0.98, "beta_wind": 0.97,
             "tail_amplification_factor": 1.4},
        3:  {"delta_temp_c": 2.6, "alpha_solar": 0.99, "beta_wind": 0.98,
             "tail_amplification_factor": 1.4},
        4:  {"delta_temp_c": 2.4, "alpha_solar": 1.00, "beta_wind": 0.99,
             "tail_amplification_factor": 1.4},
        5:  {"delta_temp_c": 2.3, "alpha_solar": 1.01, "beta_wind": 0.99,
             "tail_amplification_factor": 1.4},
        6:  {"delta_temp_c": 2.4, "alpha_solar": 1.02, "beta_wind": 1.00,
             "tail_amplification_factor": 1.4},
        7:  {"delta_temp_c": 2.5, "alpha_solar": 1.03, "beta_wind": 1.00,
             "tail_amplification_factor": 1.4},
        8:  {"delta_temp_c": 2.6, "alpha_solar": 1.03, "beta_wind": 1.00,
             "tail_amplification_factor": 1.4},
        9:  {"delta_temp_c": 2.5, "alpha_solar": 1.01, "beta_wind": 1.00,
             "tail_amplification_factor": 1.4},
        10: {"delta_temp_c": 2.4, "alpha_solar": 1.00, "beta_wind": 0.99,
             "tail_amplification_factor": 1.4},
        11: {"delta_temp_c": 2.6, "alpha_solar": 0.99, "beta_wind": 0.98,
             "tail_amplification_factor": 1.4},
        12: {"delta_temp_c": 2.8, "alpha_solar": 0.98, "beta_wind": 0.97,
             "tail_amplification_factor": 1.4},
    },
}

_SCENARIO_ALIASES: Dict[str, str] = {
    "ssp5-8.5": "SSP5-8.5",
    "ssp585":   "SSP5-8.5",
    "rcp8.5":   "SSP5-8.5",
    "ssp2-4.5": "SSP2-4.5",
    "ssp245":   "SSP2-4.5",
    "rcp4.5":   "SSP2-4.5",
}


def _normalise_scenario(scenario: str) -> str:
    """Return the canonical scenario key, or raise ValueError."""
    normalised = _SCENARIO_ALIASES.get(scenario.lower())
    if normalised is not None:
        return normalised
    if scenario in _ANOMALIES_2100:
        return scenario
    available = ", ".join(sorted(_ANOMALIES_2100.keys()))
    raise ValueError(
        f"Unknown climate scenario '{scenario}'. "
        f"Available scenarios: {available}"
    )


def get_monthly_anomalies(
    scenario: str,
    target_year: int,
    baseline_year: int = 1980,
) -> Dict[int, Dict[str, float]]:
    """Return per-month climate anomaly deltas interpolated to *target_year*.

    Parameters
    ----------
    scenario : str
        CMIP6 scenario string, e.g. 'SSP5-8.5' or 'ssp585'.
    target_year : int
        Future year for which deltas are required (e.g. 2050).
        Must be in the range [2025, 2100].
    baseline_year : int
        Reference period year encoded in the source EPW (default 1980).

    Returns
    -------
    Dict[int, Dict[str, float]]
        Keys are month numbers 1-12.
    """
    canon = _normalise_scenario(scenario)

    if not (2025 <= target_year <= 2100):
        raise ValueError(
            f"target_year must be between 2025 and 2100, got {target_year}."
        )
    if baseline_year >= 2100:
        raise ValueError(
            f"baseline_year must be less than 2100, got {baseline_year}."
        )

    scale: float = (target_year - baseline_year) / (2100 - baseline_year)

    ref_table = _ANOMALIES_2100[canon]
    result: Dict[int, Dict[str, float]] = {}

    for month, ref in ref_table.items():
        delta_temp = ref["delta_temp_c"] * scale
        alpha_solar = 1.0 + (ref["alpha_solar"] - 1.0) * scale
        beta_wind = 1.0 + (ref["beta_wind"] - 1.0) * scale
        tail_factor = ref["tail_amplification_factor"]

        result[month] = {
            "delta_temp_c":              round(delta_temp,  6),
            "alpha_solar":               round(alpha_solar, 6),
            "beta_wind":                 round(beta_wind,   6),
            "tail_amplification_factor": tail_factor,
        }

    return result


# ---------------------------------------------------------------------------
# Anomaly detection functions
# ---------------------------------------------------------------------------

def flag_anomalies(
    df: pd.DataFrame,
    columns: Optional[List[str]] = None,
    z_threshold: float = 3.5,
) -> pd.DataFrame:
    """Flag statistical outliers using a z-score threshold.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    columns : list of str, optional
        Columns to check. Defaults to all numeric columns present in *df*.
    z_threshold : float
        Absolute z-score above which a value is considered an anomaly.

    Returns
    -------
    pd.DataFrame
        Copy of *df* with additional ``<col>_anomaly`` boolean columns.
    """
    result = df.copy()

    if columns is None:
        columns = list(df.select_dtypes(include=[np.number]).columns)

    for col in columns:
        if col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        std = series.std()
        if std == 0 or np.isnan(std):
            result[f"{col}_anomaly"] = np.zeros(len(df), dtype=bool)
            continue
        z = (series - series.mean()).abs() / std
        result[f"{col}_anomaly"] = (z > z_threshold).astype(bool)

    return result


def check_physical_bounds(
    df: pd.DataFrame,
    bounds: Optional[Dict[str, Tuple[float, float]]] = None,
) -> pd.DataFrame:
    """Flag values that fall outside physically plausible ranges.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    bounds : dict, optional
        Mapping ``{column_name: (lower, upper)}``. If not supplied the
        module-level ``_DEFAULT_BOUNDS`` table is used.

    Returns
    -------
    pd.DataFrame
        Copy of *df* with additional ``<col>_out_of_bounds`` boolean columns.
    """
    result = df.copy()
    effective_bounds = bounds if bounds is not None else _DEFAULT_BOUNDS

    for col, (lo, hi) in effective_bounds.items():
        if col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        out = ((series < lo) | (series > hi)).astype(bool)
        result[f"{col}_out_of_bounds"] = out

    return result


def detect_wind_anomalies(
    df: pd.DataFrame,
    calm_threshold: float = 0.5,
) -> pd.DataFrame:
    """Detect wind-specific anomalies in a DataFrame.

    Adds three boolean flag columns:
    - ``wind_speed_unphysical``: wind speed < 0
    - ``wind_direction_out_of_range``: direction outside [0, 360]
    - ``wind_calm_direction_inconsistency``: calm wind with non-zero direction

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    calm_threshold : float
        Wind speeds below this value (m/s) are considered calm. Default 0.5.

    Returns
    -------
    pd.DataFrame
        Copy of *df* with the three flag columns added.
    """
    result = df.copy()
    n = len(df)

    if "wind_speed" in df.columns:
        ws = pd.to_numeric(df["wind_speed"], errors="coerce").fillna(0.0)
        result["wind_speed_unphysical"] = (ws < 0.0).astype(bool)
    else:
        result["wind_speed_unphysical"] = np.zeros(n, dtype=bool)

    if "wind_direction" in df.columns:
        wd = pd.to_numeric(df["wind_direction"], errors="coerce").fillna(0.0)
        result["wind_direction_out_of_range"] = (
            (wd < 0.0) | (wd > 360.0)
        ).astype(bool)
    else:
        result["wind_direction_out_of_range"] = np.zeros(n, dtype=bool)

    if "wind_speed" in df.columns and "wind_direction" in df.columns:
        ws = pd.to_numeric(df["wind_speed"], errors="coerce").fillna(0.0)
        wd = pd.to_numeric(df["wind_direction"], errors="coerce").fillna(0.0)
        is_calm = ws < calm_threshold
        has_direction = wd != 0.0
        result["wind_calm_direction_inconsistency"] = (
            is_calm & has_direction
        ).astype(bool)
    else:
        result["wind_calm_direction_inconsistency"] = np.zeros(n, dtype=bool)

    return result


def summarise_anomalies(df: pd.DataFrame) -> Dict[str, int]:
    """Return a count of flagged anomalies for each anomaly/flag column.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing boolean flag columns.

    Returns
    -------
    Dict[str, int]
        Mapping of column name -> count of True values.
    """
    flag_cols = [
        c for c in df.columns
        if c.endswith("_anomaly")
        or c.endswith("_out_of_bounds")
        or c.endswith("_unphysical")
        or c.endswith("_out_of_range")
        or c.endswith("_inconsistency")
    ]
    return {col: int(df[col].sum()) for col in flag_cols}