"""Quality checks for EPW data: outliers and physical bounds."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

DEFAULT_BOUNDS: Dict[str, Tuple[float, float]] = {
    "dry_bulb_temperature": (-70.0, 70.0),
    "dew_point_temperature": (-70.0, 70.0),
    "relative_humidity": (0.0, 110.0),
    "atmospheric_pressure": (31000.0, 120000.0),
    "global_horizontal_radiation": (0.0, 1500.0),
    "direct_normal_radiation": (0.0, 1500.0),
    "diffuse_horizontal_radiation": (0.0, 1500.0),
    "wind_direction": (0.0, 360.0),
    "wind_speed": (0.0, 40.0),
}
"""EnergyPlus' accepted ranges for the morphed fields."""

_FLAG_SUFFIXES = ("_anomaly", "_out_of_bounds", "_unphysical", "_out_of_range", "_inconsistency")


def flag_anomalies(
    df: pd.DataFrame,
    columns: Optional[List[str]] = None,
    z_threshold: float = 3.5,
) -> pd.DataFrame:
    """Add ``<col>_anomaly`` columns flagging |z| > *z_threshold*."""
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
        else:
            result[f"{col}_anomaly"] = ((series - series.mean()).abs() / std > z_threshold).astype(
                bool
            )
    return result


def check_physical_bounds(
    df: pd.DataFrame,
    bounds: Optional[Dict[str, Tuple[float, float]]] = None,
) -> pd.DataFrame:
    """Add ``<col>_out_of_bounds`` columns (default: :data:`DEFAULT_BOUNDS`)."""
    result = df.copy()
    for col, (lo, hi) in (bounds or DEFAULT_BOUNDS).items():
        if col in df.columns:
            series = pd.to_numeric(df[col], errors="coerce")
            result[f"{col}_out_of_bounds"] = ((series < lo) | (series > hi)).astype(bool)
    return result


def detect_wind_anomalies(df: pd.DataFrame, calm_threshold: float = 0.5) -> pd.DataFrame:
    """Flag negative speeds, directions outside 0-360 and calm hours with a direction."""
    result = df.copy()
    zeros = np.zeros(len(df), dtype=bool)
    has_ws = "wind_speed" in df.columns
    has_wd = "wind_direction" in df.columns
    ws = pd.to_numeric(df["wind_speed"], errors="coerce").fillna(0.0) if has_ws else None
    wd = pd.to_numeric(df["wind_direction"], errors="coerce").fillna(0.0) if has_wd else None

    result["wind_speed_unphysical"] = (ws < 0.0).astype(bool) if has_ws else zeros
    result["wind_direction_out_of_range"] = (
        ((wd < 0.0) | (wd > 360.0)).astype(bool) if has_wd else zeros
    )
    result["wind_calm_direction_inconsistency"] = (
        ((ws < calm_threshold) & (wd != 0.0)).astype(bool) if has_ws and has_wd else zeros
    )
    return result


def summarise_anomalies(df: pd.DataFrame) -> Dict[str, int]:
    """Count ``True`` values in each flag column."""
    return {c: int(df[c].sum()) for c in df.columns if c.endswith(_FLAG_SUFFIXES)}
