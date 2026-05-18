"""EPW file parser and writer."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Union

import pandas as pd

logger = logging.getLogger(__name__)

NUM_HEADER_LINES = 8

EPW_COLUMNS = [
    "year",
    "month",
    "day",
    "hour",
    "minute",
    "data_flags",
    "dry_bulb_temperature",
    "dew_point_temperature",
    "relative_humidity",
    "atmospheric_pressure",
    "extraterrestrial_horizontal_radiation",
    "extraterrestrial_direct_normal_radiation",
    "horizontal_infrared_radiation_intensity",
    "global_horizontal_radiation",
    "direct_normal_radiation",
    "diffuse_horizontal_radiation",
    "global_horizontal_illuminance",
    "direct_normal_illuminance",
    "diffuse_horizontal_illuminance",
    "zenith_luminance",
    "wind_direction",
    "wind_speed",
    "total_sky_cover",
    "opaque_sky_cover",
    "visibility",
    "ceiling_height",
    "present_weather_observation",
    "present_weather_codes",
    "precipitable_water",
    "aerosol_optical_depth",
    "snow_depth",
    "days_since_last_snowfall",
    "albedo",
    "liquid_precipitation_depth",
    "liquid_precipitation_quantity",
]


def parse_epw(path: Union[str, Path]) -> tuple[list[str], pd.DataFrame]:
    """Parse an EPW weather file into header lines and a data DataFrame.

    Parameters
    ----------
    path:
        Path to the ``.epw`` file.

    Returns
    -------
    tuple[list[str], pd.DataFrame]
        A 2-tuple of (header_lines, data_frame).  ``header_lines`` is a list
        of the raw header strings (length == NUM_HEADER_LINES).  ``data_frame``
        has columns defined by :data:`EPW_COLUMNS`.
    """
    path = Path(path)
    logger.debug("Parsing EPW file: %s", path)

    header_lines: list[str] = []
    data_rows: list[list[str]] = []

    with path.open(newline="", encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if i < NUM_HEADER_LINES:
                header_lines.append(line.rstrip("\n"))
            else:
                row = next(csv.reader([line]))
                data_rows.append(row)

    if not data_rows:
        raise ValueError(f"No data rows found in EPW file: {path}")

    df = pd.DataFrame(data_rows, columns=EPW_COLUMNS)

    numeric_cols = [c for c in EPW_COLUMNS if c not in ("data_flags",)]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    logger.debug("Parsed %d data rows from %s", len(df), path)
    return header_lines, df


def parse_epw_meta(path: Union[str, Path]) -> dict[str, str]:
    """Parse the LOCATION header line of an EPW file into a metadata dict.

    Parameters
    ----------
    path:
        Path to the ``.epw`` file.

    Returns
    -------
    dict[str, str]
        Dictionary with keys: ``city``, ``state``, ``country``,
        ``data_type``, ``wmo_number``, ``latitude``, ``longitude``,
        ``time_zone``, ``elevation``.
    """
    path = Path(path)
    with path.open(encoding="utf-8") as fh:
        location_line = fh.readline().rstrip("\n")

    parts = location_line.split(",")
    keys = [
        "record_type",
        "city",
        "state",
        "country",
        "data_type",
        "wmo_number",
        "latitude",
        "longitude",
        "time_zone",
        "elevation",
    ]
    meta: dict[str, str] = {}
    for key, value in zip(keys, parts):
        if key == "record_type":
            continue
        meta[key] = value.strip()
    return meta


def write_epw(
    path: Union[str, Path],
    header_lines: list[str],
    df: pd.DataFrame,
) -> None:
    """Write a morphed DataFrame back to an EPW file.

    Parameters
    ----------
    path:
        Destination path for the output ``.epw`` file.
    header_lines:
        List of raw header strings (length == NUM_HEADER_LINES).
    df:
        Data DataFrame with columns matching :`EPW_COLUMNS`.
    """
    path = Path(path)
    logger.debug("Writing EPW file: %s", path)

    with path.open("w", newline="", encoding="utf-8") as fh:
        for line in header_lines:
            fh.write(line + "\n")

        writer = csv.writer(fh, lineterminator="\n")
        for _, row in df.iterrows():
            writer.writerow([row[col] for col in EPW_COLUMNS])

    logger.debug("Wrote %d data rows to %s", len(df), path)