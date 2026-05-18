"""Climate-change morphing of EPW weather data.

Implements the Belcher, Hacker & Powell (2005) morphing methodology:
  - Additive shift      : x_future = x_baseline + delta_x
  - Multiplicative      : x_future = alpha * x_baseline
  - Combined (temp)     : x_future = x_baseline + delta_x
                          + alpha * (x_baseline - x_monthly_mean)

Monthly deltas/alphas are expanded to 8760 hourly values via the
``month`` column that the EPW parser always produces.

Column name constants here MUST match the names in parser.EPW_COLUMNS.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Union

import numpy as np
import pandas as pd

from epwupgrader.psychrometrics import (
    recalculate_dew_point_after_temp_shift,
    recalculate_rh_after_temp_shift,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Column name constants — must match parser.EPW_COLUMNS exactly
# ---------------------------------------------------------------------------
COL_DRY_BULB: str = "dry_bulb_temperature"
COL_DEW_POINT: str = "dew_point_temperature"
COL_RH: str = "relative_humidity"
COL_PRESSURE: str = "atmospheric_pressure"
COL_GHI: str = "global_horizontal_radiation"
COL_DNI: str = "direct_normal_radiation"
COL_DHI: str = "diffuse_horizontal_radiation"
COL_WIND_SPEED: str = "wind_speed"
COL_MONTH: str = "month"


def _check_column(df: pd.DataFrame, col: str, caller: str) -> None:
    """Raise KeyError with a descriptive message when *col* is absent."""
    if col not in df.columns:
        raise KeyError(
            f"{caller}: required column {col!r} not found. "
            f"Available: {list(df.columns)}"
        )


def _resolve_delta(
    delta: Union[np.ndarray, list, float, int],
    df: pd.DataFrame,
) -> np.ndarray:
    """Resolve a delta/alpha argument into a 1-D float array of len(df).

    Accepts:
    * scalar              -> broadcast to ``len(df)``
    * length-12 array     -> expanded monthly->hourly via ``month`` column
    * length-N array      -> used as-is (must equal ``len(df)``)
    """
    arr = np.asarray(delta, dtype=float)
    if arr.ndim == 0:
        return np.full(len(df), float(delta))
    if arr.shape[0] == 12 and len(df) != 12:
        month_indices = df[COL_MONTH].to_numpy(dtype=int) - 1
        return arr[month_indices]
    if arr.shape[0] != len(df):
        raise ValueError(
            f"delta/alpha length {arr.shape[0]} does not match DataFrame "
            f"length {len(df)} and is not 12 (monthly)."
        )
    return arr


def _monthly_means(df: pd.DataFrame, col: str) -> np.ndarray:
    """Return per-row monthly mean of *col*.

    Returns an array (length == len(df)) where each element is the mean
    of *col* for that row's calendar month. Uses the ``month`` column.
    """
    _check_column(df, COL_MONTH, "_monthly_means")
    means = df.groupby(COL_MONTH)[col].transform("mean")
    return means.to_numpy(dtype=float)


def apply_temperature_morphing(
    temperature: float,
    delta_t: float,
    alpha: float,
    t_mean: float,
) -> float:
    """Apply scalar temperature morphing (combined shift + stretch).

    Formula: T_future = T + delta_t + 0.5 * alpha * (T - t_mean)

    Parameters
    ----------
    temperature : float
        Baseline temperature in degrees Celsius.
    delta_t : float
        Absolute temperature shift in degrees Celsius.
    alpha : float
        Fractional change coefficient for the stretch term.
    t_mean : float
        Monthly mean baseline temperature in degrees Celsius.

    Returns
    -------
    float
        Morphed temperature in degrees Celsius.
    """
    return temperature + delta_t + 0.5 * alpha * (temperature - t_mean)


def apply_wind_morphing(wind_speed: float, scale_factor: float) -> float:
    """Apply multiplicative morphing to a scalar wind speed value.

    Result is clamped to >= 0.

    Parameters
    ----------
    wind_speed : float
        Baseline wind speed in m/s.
    scale_factor : float
        Multiplicative scaling factor.

    Returns
    -------
    float
        Morphed wind speed in m/s, >= 0.
    """
    return max(0.0, wind_speed * scale_factor)


def apply_precipitation_morphing(
    precipitation: float,
    scale_factor: float,
) -> float:
    """Apply multiplicative morphing to a scalar precipitation value.

    Result is clamped to >= 0.

    Parameters
    ----------
    precipitation : float
        Baseline precipitation value.
    scale_factor : float
        Multiplicative scaling factor.

    Returns
    -------
    float
        Morphed precipitation value, >= 0.
    """
    return max(0.0, precipitation * scale_factor)


def morph_temperature(
    df: pd.DataFrame,
    delta_t: Union[np.ndarray, list, float],
    alpha_t: Optional[Union[np.ndarray, list, float]] = None,
) -> pd.DataFrame:
    """Morph dry-bulb temperature and recalculate psychrometric fields.

    After shifting T_db, dew-point and RH are recalculated holding actual
    vapour pressure constant (Belcher et al. 2005 assumption).

    Formula when alpha_t is supplied (Belcher eq. 3):
        T_future = T + delta_T + alpha_T * (T - T_monthly_mean)

    Formula when alpha_t is None (Belcher eq. 1, pure additive shift):
        T_future = T + delta_T

    Parameters
    ----------
    df : pd.DataFrame
        Baseline EPW data.
    delta_t : scalar or array-like
        Absolute temperature change in degC. Can be a scalar, a
        length-12 monthly array, or a length-8760 hourly array.
    alpha_t : scalar or array-like, optional
        Fractional change coefficient for combined morphing (eq. 3).

    Returns
    -------
    pd.DataFrame
        Copy with ``dry_bulb_temperature``, ``dew_point_temperature``,
        and ``relative_humidity`` updated.
    """
    result = df.copy()
    _check_column(result, COL_DRY_BULB, "morph_temperature")
    _check_column(result, COL_DEW_POINT, "morph_temperature")
    _check_column(result, COL_RH, "morph_temperature")

    # Save original dew point BEFORE any shift — this encodes conserved
    # actual vapour pressure used in the psychrometric recalculation below.
    original_dew_point = result[COL_DEW_POINT].to_numpy(dtype=float)
    t_values = result[COL_DRY_BULB].to_numpy(dtype=float)
    d_t = _resolve_delta(delta_t, result)

    if alpha_t is not None:
        a_t = _resolve_delta(alpha_t, result)
        monthly_means = _monthly_means(result, COL_DRY_BULB)
        new_t = t_values + d_t + a_t * (t_values - monthly_means)
    else:
        new_t = t_values + d_t

    result[COL_DRY_BULB] = new_t

    # Psychrometric recalculation — mandatory after every temperature shift.
    # Actual vapour pressure is conserved; RH and dew-point must fall as
    # saturation VP rises exponentially with temperature (Clausius-Clapeyron).
    result[COL_RH] = recalculate_rh_after_temp_shift(original_dew_point, new_t)
    result[COL_DEW_POINT] = recalculate_dew_point_after_temp_shift(
        original_dew_point, new_t
    )
    return result


def morph_radiation(
    df: pd.DataFrame,
    alpha_ghi: Union[np.ndarray, list, float],
    alpha_dni: Optional[Union[np.ndarray, list, float]] = None,
    alpha_dhi: Optional[Union[np.ndarray, list, float]] = None,
) -> pd.DataFrame:
    """Morph solar radiation fields using multiplicative morphing.

    R_future = alpha_R * R_baseline   (clipped to >= 0)

    Negative values are physically impossible and would cause EnergyPlus
    to abort, so results are hard-clipped to zero.

    Parameters
    ----------
    df : pd.DataFrame
        Baseline EPW data.
    alpha_ghi : scalar or array-like
        Multiplier for global horizontal irradiance.
    alpha_dni : scalar or array-like, optional
        Multiplier for direct normal irradiance.
    alpha_dhi : scalar or array-like, optional
        Multiplier for diffuse horizontal irradiance.

    Returns
    -------
    pd.DataFrame
        Copy with radiation columns morphed and floor-clamped to 0.
    """
    result = df.copy()

    def _apply_rad(col: str, alpha: Union[np.ndarray, list, float]) -> None:
        if col not in result.columns:
            logger.warning("morph_radiation: column %r not found; skipping.", col)
            return
        values = result[col].to_numpy(dtype=float)
        a = _resolve_delta(alpha, result)
        result[col] = np.clip(values * a, 0.0, None)

    _apply_rad(COL_GHI, alpha_ghi)
    if alpha_dni is not None:
        _apply_rad(COL_DNI, alpha_dni)
    if alpha_dhi is not None:
        _apply_rad(COL_DHI, alpha_dhi)

    return result


def morph_wind_speed(
    df: pd.DataFrame,
    alpha_ws: Union[np.ndarray, list, float],
) -> pd.DataFrame:
    """Morph wind speed using multiplicative morphing, clipped to >= 0.

    WS_future = alpha_WS * WS_baseline

    Parameters
    ----------
    df : pd.DataFrame
        Baseline EPW data containing ``wind_speed``.
    alpha_ws : scalar or array-like
        Fractional multiplier for wind speed.

    Returns
    -------
    pd.DataFrame
        Copy with ``wind_speed`` morphed.
    """
    result = df.copy()
    _check_column(result, COL_WIND_SPEED, "morph_wind_speed")
    values = result[COL_WIND_SPEED].to_numpy(dtype=float)
    a = _resolve_delta(alpha_ws, result)
    result[COL_WIND_SPEED] = np.clip(values * a, 0.0, None)
    return result


def morph_pressure(
    df: pd.DataFrame,
    delta_p: Union[np.ndarray, list, float],
) -> pd.DataFrame:
    """Morph atmospheric pressure using an additive shift.

    Parameters
    ----------
    df : pd.DataFrame
        Baseline EPW data containing ``atmospheric_pressure``.
    delta_p : scalar or array-like
        Absolute pressure change in Pa.

    Returns
    -------
    pd.DataFrame
        Copy with ``atmospheric_pressure`` morphed.
    """
    result = df.copy()
    _check_column(result, COL_PRESSURE, "morph_pressure")
    values = result[COL_PRESSURE].to_numpy(dtype=float)
    d_p = _resolve_delta(delta_p, result)
    result[COL_PRESSURE] = values + d_p
    return result


def apply_all_morphing(
    df: pd.DataFrame,
    deltas: Dict[str, Union[np.ndarray, list, float]],
    alphas: Optional[Dict[str, Union[np.ndarray, list, float]]] = None,
) -> pd.DataFrame:
    """Apply a complete set of morphing operations in one call.

    Parameters
    ----------
    df : pd.DataFrame
        Baseline EPW data.
    deltas : dict
        Mapping of ``{field_name: delta_value}`` for additive morphing.
        Recognised keys: ``"dry_bulb_temperature"``,
        ``"dew_point_temperature"``, ``"atmospheric_pressure"``.
    alphas : dict, optional
        Mapping of ``{field_name: alpha_value}`` for multiplicative
        morphing. Recognised keys: ``"dry_bulb_temperature"`` (combined),
        ``"global_horizontal_radiation"``,
        ``"direct_normal_radiation"``,
        ``"diffuse_horizontal_radiation"``, ``"wind_speed"``.

    Returns
    -------
    pd.DataFrame
        Morphed copy of *df* with identical index.
    """
    if alphas is None:
        alphas = {}

    result = df.copy()

    if COL_DRY_BULB in deltas:
        result = morph_temperature(
            result,
            delta_t=deltas[COL_DRY_BULB],
            alpha_t=alphas.get(COL_DRY_BULB),
        )

    if COL_DEW_POINT in deltas:
        result = morph_temperature(
            result,
            delta_t=deltas[COL_DEW_POINT],
            alpha_t=None,
        )

    if COL_PRESSURE in deltas:
        result = morph_pressure(result, delta_p=deltas[COL_PRESSURE])

    if COL_GHI in alphas:
        result = morph_radiation(
            result,
            alpha_ghi=alphas[COL_GHI],
            alpha_dni=alphas.get(COL_DNI),
            alpha_dhi=alphas.get(COL_DHI),
        )

    if COL_WIND_SPEED in alphas:
        result = morph_wind_speed(result, alpha_ws=alphas[COL_WIND_SPEED])

    return result