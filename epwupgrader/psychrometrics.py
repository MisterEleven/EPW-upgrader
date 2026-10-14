"""Psychrometric helpers (SI units, temperatures in degC, RH in %).

Saturation vapour pressure uses the Magnus formula with Alduchov &
Eskridge (1996) coefficients, accurate to ~0.1 % for -40..+60 degC.
"""

from __future__ import annotations

import math

import numpy as np

_A = 17.625
_B = 243.04  # degC
_E0 = 611.2  # Pa, e_s at 0 degC

_DP_LOWER_BOUND = -80.0


def saturation_vapour_pressure(temp_c: float) -> float:
    """Saturation vapour pressure [Pa]."""
    return float(_E0 * math.exp(_A * temp_c / (_B + temp_c)))


def vapour_pressure_from_rh(dry_bulb_c: float, rh_pct: float) -> float:
    """Actual vapour pressure [Pa]; RH is clamped to 0..100."""
    rh = max(0.0, min(100.0, rh_pct))
    return saturation_vapour_pressure(dry_bulb_c) * rh / 100.0


def vapour_pressure_from_dew_point(dew_point_c: float) -> float:
    """Actual vapour pressure [Pa]."""
    return saturation_vapour_pressure(dew_point_c)


def dew_point_from_rh(dry_bulb_c: float, rh_pct: float) -> float:
    """Dew point [degC], capped at dry bulb; -80 for RH <= 0."""
    if rh_pct <= 0.0:
        return _DP_LOWER_BOUND
    alpha = math.log(min(rh_pct, 100.0) / 100.0) + _A * dry_bulb_c / (_B + dry_bulb_c)
    return min(_B * alpha / (_A - alpha), dry_bulb_c)


def dew_point_from_vapour_pressure(vapour_pressure_pa: float) -> float:
    """Dew point [degC]; -80 for non-positive input."""
    if vapour_pressure_pa <= 0.0:
        return _DP_LOWER_BOUND
    ln_ratio = math.log(vapour_pressure_pa / _E0)
    return _B * ln_ratio / (_A - ln_ratio)


def rh_from_dew_point(dry_bulb_c: float, dew_point_c: float) -> float:
    """Relative humidity [%], clamped to 1..100."""
    e_sat = saturation_vapour_pressure(dry_bulb_c)
    if e_sat <= 0.0:
        return 100.0
    rh = 100.0 * saturation_vapour_pressure(dew_point_c) / e_sat
    return float(max(1.0, min(100.0, rh)))


def rh_from_vapour_pressures(
    actual_vapour_pressure_pa: float,
    saturation_vapour_pressure_pa: float,
) -> float:
    """Relative humidity [%], clamped to 0..100."""
    if saturation_vapour_pressure_pa <= 0.0:
        return 0.0
    rh = 100.0 * actual_vapour_pressure_pa / saturation_vapour_pressure_pa
    return float(max(0.0, min(100.0, rh)))


def wet_bulb_temperature(dry_bulb_c: float, rh_pct: float) -> float:
    """Wet bulb [degC] via Stull (2011), capped at dry bulb."""
    rh = max(0.0, min(100.0, rh_pct))
    wb = (
        dry_bulb_c * math.atan(0.151977 * math.sqrt(rh + 8.313659))
        + math.atan(dry_bulb_c + rh)
        - math.atan(rh - 1.676331)
        + 0.00391838 * rh**1.5 * math.atan(0.023101 * rh)
        - 4.686035
    )
    return float(min(wb, dry_bulb_c))


def humidity_ratio(dry_bulb_c: float, rh_pct: float) -> float:
    """Humidity ratio [kg/kg] at standard pressure (101325 Pa)."""
    e = vapour_pressure_from_rh(dry_bulb_c, rh_pct)
    return 0.62198 * e / max(1.0, 101325.0 - e)


def enthalpy(dry_bulb_c: float, rh_pct: float) -> float:
    """Moist-air enthalpy [kJ/kg dry air]."""
    w = humidity_ratio(dry_bulb_c, rh_pct)
    return 1.006 * dry_bulb_c + w * (2501.0 + 1.86 * dry_bulb_c)


def recalculate_rh_after_temp_shift(
    original_dew_point: np.ndarray,
    new_dry_bulb: np.ndarray,
) -> np.ndarray:
    """RH [%] after a dry-bulb change at constant vapour pressure."""
    tdp = np.asarray(original_dew_point, dtype=float)
    tdb = np.asarray(new_dry_bulb, dtype=float)
    e_actual = _E0 * np.exp(_A * tdp / (_B + tdp))
    e_sat = _E0 * np.exp(_A * tdb / (_B + tdb))
    return np.clip(100.0 * e_actual / e_sat, 0.0, 100.0)


def scale_rh_for_temp_shift(
    rh: np.ndarray,
    old_dry_bulb: np.ndarray,
    new_dry_bulb: np.ndarray,
) -> np.ndarray:
    """RH [%] after a dry-bulb change at constant vapour pressure.

    Scales the source RH by ``e_s(T) / e_s(T')``. Unlike recomputing from the dew
    point, this cannot raise RH when the source RH and dew point disagree.
    """
    t0 = np.asarray(old_dry_bulb, dtype=float)
    t1 = np.asarray(new_dry_bulb, dtype=float)
    ratio = np.exp(_A * t0 / (_B + t0) - _A * t1 / (_B + t1))
    return np.clip(np.asarray(rh, dtype=float) * ratio, 0.0, 100.0)


def recalculate_dew_point_after_temp_shift(
    original_dew_point: np.ndarray,
    new_dry_bulb: np.ndarray,
) -> np.ndarray:
    """Dew point after a dry-bulb change: unchanged, capped at the new dry bulb."""
    tdp = np.asarray(original_dew_point, dtype=float)
    tdb = np.asarray(new_dry_bulb, dtype=float)
    return np.where(np.isnan(tdb), tdp, np.minimum(tdp, tdb))
