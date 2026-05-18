"""Psychrometric calculations for epwupgrader.

All functions operate on scalar float values (in SI units) unless
otherwise noted.  The Magnus-Tetens approximation is used throughout
for e_s(T) -- it is accurate to within 0.1% over the range -40 C to
+60 C, which covers all physically plausible EPW temperature values.

References
----------
- August-Roche-Magnus formula (Alduchov & Eskridge 1996)
- WMO Guide to Meteorological Instruments and Methods of Observation
  (CIMO Guide), 2018 edition
"""

from __future__ import annotations

import math

import numpy as np

# ---------------------------------------------------------------------------
# Magnus-Tetens constants (Alduchov & Eskridge 1996 formulation)
# These give e_s in Pa when T is in degrees C.
# ---------------------------------------------------------------------------
_A = 17.625   # dimensionless
_B = 243.04   # degrees C
_E0 = 611.2   # Pa  (saturation vapour pressure at 0 degrees C)

_DP_LOWER_BOUND = -80.0


def saturation_vapour_pressure(temp_c: float) -> float:
    """Compute saturation vapour pressure using the Magnus-Tetens formula.

    Parameters
    ----------
    temp_c : float
        Dry-bulb temperature in degrees Celsius.

    Returns
    -------
    float
        Saturation vapour pressure in Pascals.
    """
    return float(_E0 * math.exp(_A * temp_c / (_B + temp_c)))


def vapour_pressure_from_rh(dry_bulb_c: float, rh_pct: float) -> float:
    """Compute actual vapour pressure from dry-bulb temperature and RH.

    Parameters
    ----------
    dry_bulb_c : float
        Dry-bulb temperature in degrees Celsius.
    rh_pct : float
        Relative humidity in percent (0-100).  Values outside [0, 100] are
        clamped.

    Returns
    -------
    float
        Actual vapour pressure in Pascals.
    """
    rh_clamped = max(0.0, min(100.0, rh_pct))
    e_s = saturation_vapour_pressure(dry_bulb_c)
    return e_s * rh_clamped / 100.0


def vapour_pressure_from_dew_point(dew_point_c: float) -> float:
    """Compute actual vapour pressure from dew-point temperature.

    Parameters
    ----------
    dew_point_c : float
        Dew-point temperature in degrees Celsius.

    Returns
    -------
    float
        Actual vapour pressure in Pascals.
    """
    return saturation_vapour_pressure(dew_point_c)


def dew_point_from_rh(dry_bulb_c: float, rh_pct: float) -> float:
    """Compute dew-point temperature from dry-bulb temperature and RH.

    Parameters
    ----------
    dry_bulb_c : float
        Dry-bulb temperature in degrees Celsius.
    rh_pct : float
        Relative humidity in percent (0-100).

    Returns
    -------
    float
        Dew-point temperature in degrees Celsius.  Always <= dry_bulb_c.
        Returns -80.0 for RH <= 0.
    """
    if rh_pct <= 0.0:
        return _DP_LOWER_BOUND
    rh_frac = min(rh_pct, 100.0) / 100.0
    alpha = math.log(rh_frac) + _A * dry_bulb_c / (_B + dry_bulb_c)
    dp = _B * alpha / (_A - alpha)
    return min(dp, dry_bulb_c)


def dew_point_from_vapour_pressure(vapour_pressure_pa: float) -> float:
    """Compute dew-point temperature from actual vapour pressure.

    Parameters
    ----------
    vapour_pressure_pa : float
        Actual vapour pressure in Pascals.

    Returns
    -------
    float
        Dew-point temperature in degrees Celsius.
        Returns -80.0 for non-positive input.
    """
    if vapour_pressure_pa <= 0.0:
        return _DP_LOWER_BOUND
    ln_ratio = math.log(vapour_pressure_pa / _E0)
    return _B * ln_ratio / (_A - ln_ratio)


def rh_from_dew_point(dry_bulb_c: float, dew_point_c: float) -> float:
    """Compute relative humidity from dry-bulb and dew-point temperatures.

    Parameters
    ----------
    dry_bulb_c : float
        Dry-bulb temperature in degrees Celsius.
    dew_point_c : float
        Dew-point temperature in degrees Celsius.

    Returns
    -------
    float
        Relative humidity in percent, clamped to [1, 100].
    """
    e_sat_dry = saturation_vapour_pressure(dry_bulb_c)
    e_sat_dew = saturation_vapour_pressure(dew_point_c)
    if e_sat_dry <= 0.0:
        return 100.0
    rh = 100.0 * e_sat_dew / e_sat_dry
    return float(max(1.0, min(100.0, rh)))


def rh_from_vapour_pressures(
    actual_vapour_pressure_pa: float,
    saturation_vapour_pressure_pa: float,
) -> float:
    """Compute relative humidity from actual and saturation vapour pressures.

    Parameters
    ----------
    actual_vapour_pressure_pa : float
        Actual vapour pressure in Pascals.
    saturation_vapour_pressure_pa : float
        Saturation vapour pressure in Pascals.

    Returns
    -------
    float
        Relative humidity in percent, clamped to [0, 100].
    """
    if saturation_vapour_pressure_pa <= 0.0:
        return 0.0
    rh = 100.0 * actual_vapour_pressure_pa / saturation_vapour_pressure_pa
    return float(max(0.0, min(100.0, rh)))


def wet_bulb_temperature(dry_bulb_c: float, rh_pct: float) -> float:
    """Estimate wet-bulb temperature using Stull (2011) empirical formula.

    Parameters
    ----------
    dry_bulb_c : float
        Dry-bulb temperature in degrees Celsius.
    rh_pct : float
        Relative humidity in percent (0-100).

    Returns
    -------
    float
        Wet-bulb temperature in degrees Celsius.  Always <= dry_bulb_c.
    """
    rh = max(0.0, min(100.0, rh_pct))
    wb = (
        dry_bulb_c * math.atan(0.151977 * math.sqrt(rh + 8.313659))
        + math.atan(dry_bulb_c + rh)
        - math.atan(rh - 1.676331)
        + 0.00391838 * rh ** 1.5 * math.atan(0.023101 * rh)
        - 4.686035
    )
    return float(min(wb, dry_bulb_c))


def humidity_ratio(dry_bulb_c: float, rh_pct: float) -> float:
    """Compute humidity ratio (kg water / kg dry air).

    Uses standard atmospheric pressure (101325 Pa) as the reference
    pressure for this scalar convenience function.

    Parameters
    ----------
    dry_bulb_c : float
        Dry-bulb temperature in degrees Celsius.
    rh_pct : float
        Relative humidity in percent (0-100).

    Returns
    -------
    float
        Humidity ratio in kg_water / kg_dry_air.
    """
    p_atm = 101325.0
    e = vapour_pressure_from_rh(dry_bulb_c, rh_pct)
    return 0.62198 * e / max(1.0, p_atm - e)


def enthalpy(dry_bulb_c: float, rh_pct: float) -> float:
    """Compute moist-air specific enthalpy.

    Parameters
    ----------
    dry_bulb_c : float
        Dry-bulb temperature in degrees Celsius.
    rh_pct : float
        Relative humidity in percent (0-100).

    Returns
    -------
    float
        Specific enthalpy in kJ/kg_dry_air.
    """
    w = humidity_ratio(dry_bulb_c, rh_pct)
    return 1.006 * dry_bulb_c + w * (2501.0 + 1.86 * dry_bulb_c)


def recalculate_rh_after_temp_shift(
    original_dew_point: np.ndarray,
    new_dry_bulb: np.ndarray,
) -> np.ndarray:
    """Vectorised recalculation of RH after a dry-bulb temperature shift.

    Holds actual vapour pressure constant (determined by original dew point).

    Parameters
    ----------
    original_dew_point : array-like of float
        Pre-morph dew-point temperatures in degrees Celsius.
    new_dry_bulb : array-like of float
        Post-morph dry-bulb temperatures in degrees Celsius.

    Returns
    -------
    np.ndarray
        New relative humidity values in percent, clamped to [0, 100].
    """
    tdp = np.asarray(original_dew_point, dtype=float)
    tdb = np.asarray(new_dry_bulb, dtype=float)
    e_actual = _E0 * np.exp(_A * tdp / (_B + tdp))
    e_sat_new = _E0 * np.exp(_A * tdb / (_B + tdb))
    rh_new = np.clip(100.0 * e_actual / e_sat_new, 0.0, 100.0)
    return rh_new


def recalculate_dew_point_after_temp_shift(
    original_dew_point: np.ndarray,
    new_dry_bulb: np.ndarray,
) -> np.ndarray:
    """Vectorised recalculation of dew-point after a dry-bulb temperature shift.

    Holds actual vapour pressure constant. Dew-point is clamped so it
    never exceeds the new dry-bulb temperature.

    Parameters
    ----------
    original_dew_point : array-like of float
        Pre-morph dew-point temperatures in degrees Celsius.
    new_dry_bulb : array-like of float
        Post-morph dry-bulb temperatures in degrees Celsius.

    Returns
    -------
    np.ndarray
        New dew-point temperatures in degrees Celsius.  Always <= new_dry_bulb.
    """
    tdp = np.asarray(original_dew_point, dtype=float)
    tdb = np.asarray(new_dry_bulb, dtype=float)
    return np.minimum(tdp, tdb)