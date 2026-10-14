"""Monthly climate-change factors for morphing.

The built-in tables are illustrative, generic (not location-specific)
end-of-century changes relative to the IPCC AR6 reference period
1995-2014. For real studies, supply regional factors (e.g. CH2018 for
Switzerland) via :func:`load_anomalies_csv`.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Dict, Tuple, Union

import numpy as np

Anomalies = Dict[int, Dict[str, float]]

FIELDS = ("delta_temp_c", "alpha_solar", "beta_wind")

# Midpoint of the 1995-2014 reference period the tables are relative to.
REFERENCE_YEAR = 2005
END_YEAR = 2100

# month -> (delta_temp_c, alpha_solar, beta_wind) at END_YEAR
_TABLES_2100: Dict[str, Dict[int, Tuple[float, float, float]]] = {
    "SSP5-8.5": {
        1: (5.8, 0.97, 0.96),
        2: (5.6, 0.97, 0.96),
        3: (5.3, 0.99, 0.97),
        4: (5.0, 1.01, 0.98),
        5: (4.8, 1.03, 0.99),
        6: (4.9, 1.05, 1.00),
        7: (5.2, 1.06, 1.01),
        8: (5.4, 1.06, 1.01),
        9: (5.1, 1.03, 1.00),
        10: (4.9, 1.00, 0.99),
        11: (5.3, 0.98, 0.97),
        12: (5.7, 0.97, 0.96),
    },
    "SSP2-4.5": {
        1: (2.8, 0.98, 0.97),
        2: (2.7, 0.98, 0.97),
        3: (2.6, 0.99, 0.98),
        4: (2.4, 1.00, 0.99),
        5: (2.3, 1.01, 0.99),
        6: (2.4, 1.02, 1.00),
        7: (2.5, 1.03, 1.00),
        8: (2.6, 1.03, 1.00),
        9: (2.5, 1.01, 1.00),
        10: (2.4, 1.00, 0.99),
        11: (2.6, 0.99, 0.98),
        12: (2.8, 0.98, 0.97),
    },
}

_ALIASES = {
    "ssp5-8.5": "SSP5-8.5",
    "ssp585": "SSP5-8.5",
    "rcp8.5": "SSP5-8.5",
    "rcp85": "SSP5-8.5",
    "ssp2-4.5": "SSP2-4.5",
    "ssp245": "SSP2-4.5",
    "rcp4.5": "SSP2-4.5",
    "rcp45": "SSP2-4.5",
}

SCENARIOS = tuple(_TABLES_2100)


def normalise_scenario(scenario: str) -> str:
    """Return the canonical scenario name or raise ``ValueError``."""
    canon = _ALIASES.get(scenario.strip().lower().replace(" ", ""))
    if canon is None:
        raise ValueError(f"Unknown scenario {scenario!r}; choose from {', '.join(SCENARIOS)}.")
    return canon


def get_monthly_anomalies(
    scenario: str,
    target_year: int,
    baseline_year: int = REFERENCE_YEAR,
) -> Anomalies:
    """Return monthly factors to morph from *baseline_year* to *target_year*.

    Changes are assumed to grow linearly from REFERENCE_YEAR to END_YEAR, so
    the morph applies only the change between the two years.
    """
    table = _TABLES_2100[normalise_scenario(scenario)]
    if not 1900 <= baseline_year < END_YEAR:
        raise ValueError(f"baseline_year must be in [1900, {END_YEAR}), got {baseline_year}.")
    if not baseline_year < target_year <= END_YEAR:
        raise ValueError(
            f"target_year must be in ({baseline_year}, {END_YEAR}], got {target_year}."
        )

    scale = (target_year - baseline_year) / (END_YEAR - REFERENCE_YEAR)
    return {
        month: {
            "delta_temp_c": round(dt * scale, 6),
            "alpha_solar": round(1.0 + (a_s - 1.0) * scale, 6),
            "beta_wind": round(1.0 + (b_w - 1.0) * scale, 6),
        }
        for month, (dt, a_s, b_w) in table.items()
    }


def load_anomalies_csv(path: Union[str, Path]) -> Anomalies:
    """Load factors from a CSV with columns ``month,delta_temp_c,alpha_solar,beta_wind``.

    Values must already be relative to the EPW baseline.
    """
    result: Anomalies = {}
    with Path(path).open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        missing = {"month", *FIELDS} - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path}: missing columns {sorted(missing)}")
        for row in reader:
            month = int(row["month"])
            if month in result:
                raise ValueError(f"{path}: duplicate month {month}")
            values = {f: float(row[f]) for f in FIELDS}
            if not all(math.isfinite(v) for v in values.values()):
                raise ValueError(f"{path}: non-finite value for month {month}")
            if values["alpha_solar"] < 0 or values["beta_wind"] < 0:
                raise ValueError(f"{path}: negative scaling factor for month {month}")
            result[month] = values
    if sorted(result) != list(range(1, 13)):
        raise ValueError(f"{path}: need exactly one row per month 1-12")
    return result


def to_coefficients(anomalies: Anomalies) -> Tuple[Dict[str, np.ndarray], Dict[str, np.ndarray]]:
    """Convert monthly anomalies to ``(deltas, alphas)`` for :func:`apply_all_morphing`."""

    def monthly(field: str) -> np.ndarray:
        return np.array([anomalies[m][field] for m in range(1, 13)], dtype=float)

    solar = monthly("alpha_solar")
    deltas = {"dry_bulb_temperature": monthly("delta_temp_c")}
    alphas = {
        "global_horizontal_radiation": solar,
        "direct_normal_radiation": solar,
        "diffuse_horizontal_radiation": solar,
        "wind_speed": monthly("beta_wind"),
    }
    return deltas, alphas
