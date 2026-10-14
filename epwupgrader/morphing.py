"""Belcher et al. (2005) morphing of EPW data.

- shift:          x' = x + dx
- stretch:        x' = a * x
- shift+stretch:  x' = x + dx + a * (x - mean_month(x))

Coefficients may be scalars, 12 monthly values, or one value per row.
Empty cells and EnergyPlus missing codes (e.g. 99.9, 999, 9999) are left as is.
"""

from __future__ import annotations

from typing import Dict, Optional, Union

import numpy as np
import pandas as pd

from epwupgrader.psychrometrics import (
    recalculate_dew_point_after_temp_shift,
    scale_rh_for_temp_shift,
)

Coeff = Union[np.ndarray, list, float, int]

COL_DRY_BULB = "dry_bulb_temperature"
COL_DEW_POINT = "dew_point_temperature"
COL_RH = "relative_humidity"
COL_PRESSURE = "atmospheric_pressure"
COL_GHI = "global_horizontal_radiation"
COL_DNI = "direct_normal_radiation"
COL_DHI = "diffuse_horizontal_radiation"
COL_WIND_SPEED = "wind_speed"
COL_MONTH = "month"


# EnergyPlus "missing" codes: values at or above these are not data.
MISSING_AT_OR_ABOVE = {
    COL_DRY_BULB: 99.9,
    COL_DEW_POINT: 99.9,
    COL_RH: 999.0,
    COL_PRESSURE: 999999.0,
    COL_GHI: 9999.0,
    COL_DNI: 9999.0,
    COL_DHI: 9999.0,
    COL_WIND_SPEED: 999.0,
}


def _valid(df: pd.DataFrame, col: str) -> np.ndarray:
    """Boolean mask of rows holding real data (not NaN, not a missing code)."""
    values = df[col].to_numpy(dtype=float)
    return ~np.isnan(values) & (values < MISSING_AT_OR_ABOVE.get(col, np.inf))


def _check_column(df: pd.DataFrame, col: str, caller: str) -> None:
    if col not in df.columns:
        raise KeyError(f"{caller}: required column {col!r} not found.")


def _resolve(coeff: Coeff, df: pd.DataFrame) -> np.ndarray:
    """Expand a scalar / monthly / hourly coefficient to one value per row."""
    arr = np.asarray(coeff, dtype=float)
    if arr.ndim == 0:
        return np.full(len(df), float(arr))
    if arr.shape[0] == 12 and len(df) != 12:
        _check_column(df, COL_MONTH, "_resolve")
        return arr[df[COL_MONTH].to_numpy(dtype=int) - 1]
    if arr.shape[0] != len(df):
        raise ValueError(
            f"coefficient length {arr.shape[0]} matches neither 12 months nor {len(df)} rows."
        )
    return arr


def _scale(df: pd.DataFrame, col: str, alpha: Coeff) -> None:
    values = df[col].to_numpy(dtype=float)
    scaled = np.clip(values * _resolve(alpha, df), 0.0, None)
    df[col] = np.where(_valid(df, col), scaled, values)


def morph_temperature(
    df: pd.DataFrame,
    delta_t: Coeff,
    alpha_t: Optional[Coeff] = None,
) -> pd.DataFrame:
    """Shift (and optionally stretch) dry-bulb temperature.

    RH and dew point are updated at constant vapour pressure.
    """
    for col in (COL_DRY_BULB, COL_DEW_POINT, COL_RH):
        _check_column(df, col, "morph_temperature")
    result = df.copy()

    ok_t = _valid(result, COL_DRY_BULB)
    t = result[COL_DRY_BULB].to_numpy(dtype=float)
    new_t = t + _resolve(delta_t, result)
    if alpha_t is not None:
        real_t = result[COL_DRY_BULB].where(ok_t)
        monthly_mean = real_t.groupby(result[COL_MONTH]).transform("mean").to_numpy()
        new_t = new_t + _resolve(alpha_t, result) * (t - monthly_mean)
    new_t = np.where(ok_t, new_t, t)

    rh = result[COL_RH].to_numpy(dtype=float)
    dew_point = result[COL_DEW_POINT].to_numpy(dtype=float)
    result[COL_DRY_BULB] = new_t
    result[COL_RH] = np.where(
        ok_t & _valid(result, COL_RH), scale_rh_for_temp_shift(rh, t, new_t), rh
    )
    result[COL_DEW_POINT] = np.where(
        ok_t & _valid(result, COL_DEW_POINT),
        recalculate_dew_point_after_temp_shift(dew_point, new_t),
        dew_point,
    )
    return result


def morph_radiation(
    df: pd.DataFrame,
    alpha_ghi: Coeff,
    alpha_dni: Optional[Coeff] = None,
    alpha_dhi: Optional[Coeff] = None,
) -> pd.DataFrame:
    """Scale GHI (and optionally DNI/DHI); results are clipped to >= 0."""
    result = df.copy()
    for col, alpha in ((COL_GHI, alpha_ghi), (COL_DNI, alpha_dni), (COL_DHI, alpha_dhi)):
        if alpha is not None:
            _check_column(result, col, "morph_radiation")
            _scale(result, col, alpha)
    return result


def morph_wind_speed(df: pd.DataFrame, alpha_ws: Coeff) -> pd.DataFrame:
    """Scale wind speed; results are clipped to >= 0."""
    _check_column(df, COL_WIND_SPEED, "morph_wind_speed")
    result = df.copy()
    _scale(result, COL_WIND_SPEED, alpha_ws)
    return result


def morph_pressure(df: pd.DataFrame, delta_p: Coeff) -> pd.DataFrame:
    """Shift atmospheric pressure by *delta_p* Pa."""
    _check_column(df, COL_PRESSURE, "morph_pressure")
    result = df.copy()
    values = result[COL_PRESSURE].to_numpy(dtype=float)
    shifted = values + _resolve(delta_p, result)
    result[COL_PRESSURE] = np.where(_valid(result, COL_PRESSURE), shifted, values)
    return result


def apply_all_morphing(
    df: pd.DataFrame,
    deltas: Dict[str, Coeff],
    alphas: Optional[Dict[str, Coeff]] = None,
) -> pd.DataFrame:
    """Apply several morphs at once.

    ``deltas`` keys: dry_bulb_temperature, atmospheric_pressure.
    ``alphas`` keys: dry_bulb_temperature (stretch), global/direct_normal/
    diffuse_horizontal_radiation, wind_speed.
    """
    alphas = alphas or {}
    result = df.copy()
    if COL_DRY_BULB in deltas:
        result = morph_temperature(result, deltas[COL_DRY_BULB], alphas.get(COL_DRY_BULB))
    if COL_PRESSURE in deltas:
        result = morph_pressure(result, deltas[COL_PRESSURE])
    if any(c in alphas for c in (COL_GHI, COL_DNI, COL_DHI)):
        result = morph_radiation(
            result,
            alpha_ghi=alphas.get(COL_GHI),
            alpha_dni=alphas.get(COL_DNI),
            alpha_dhi=alphas.get(COL_DHI),
        )
    if COL_WIND_SPEED in alphas:
        result = morph_wind_speed(result, alphas[COL_WIND_SPEED])
    return result
