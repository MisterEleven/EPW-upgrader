"""Read EPW files."""

from __future__ import annotations

import csv
import logging
import re
from pathlib import Path
from typing import Optional, Union

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

# Kept as text: flags are alphanumeric, weather codes carry leading zeros.
STRING_COLUMNS = ("data_flags", "present_weather_codes")

_PERIOD_RE = re.compile(r"Period of Record\s*=\s*(\d{4})\s*-\s*(\d{4})")


# A full-year hourly EPW is ~1.6 MB; sub-hourly files can be several times larger.
MAX_FILE_BYTES = 64 * 1024 * 1024


RAW_ATTR = "epw_raw_rows"


class RawRows(tuple):
    """Source text of each data row, kept in ``df.attrs`` so unchanged cells are
    written back verbatim. Immutable, so pandas' attrs deep-copy can share it."""

    def __deepcopy__(self, memo):
        return self


def _read_lines(path: Path) -> list[str]:
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f"{path} exceeds {MAX_FILE_BYTES // 2**20} MB; not an EPW file?")
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        # Older EPWs often use Latin-1 station names.
        return path.read_text(encoding="latin-1").splitlines()


def parse_epw(path: Union[str, Path]) -> tuple[list[str], pd.DataFrame]:
    """Return ``(header_lines, df)`` for an EPW file."""
    path = Path(path)
    lines = _read_lines(path)
    if len(lines) <= NUM_HEADER_LINES:
        raise ValueError(f"No data rows found in EPW file: {path}")

    header_lines = lines[:NUM_HEADER_LINES]
    if not header_lines[0].startswith("LOCATION"):
        raise ValueError(f"Not an EPW file (missing LOCATION header): {path}")

    rows = []
    extra_fields = 0
    for lineno, line in enumerate(lines[NUM_HEADER_LINES:], NUM_HEADER_LINES + 1):
        if not line.strip():
            continue
        row = next(csv.reader([line]))
        if len(row) < len(EPW_COLUMNS):
            raise ValueError(f"{path}:{lineno}: expected {len(EPW_COLUMNS)} fields, got {len(row)}")
        extra_fields += len(row) > len(EPW_COLUMNS)
        rows.append(tuple(row[: len(EPW_COLUMNS)]))
    if extra_fields:
        logger.warning(
            "%s: dropped fields beyond %d on %d rows", path, len(EPW_COLUMNS), extra_fields
        )

    df = pd.DataFrame(rows, columns=EPW_COLUMNS)
    for col in EPW_COLUMNS:
        if col not in STRING_COLUMNS:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
    if not df["month"].between(1, 12).all():
        raise ValueError(f"{path}: month values must be 1-12")
    df.attrs[RAW_ATTR] = RawRows(rows)
    return header_lines, df


def parse_epw_meta(path: Union[str, Path]) -> dict[str, str]:
    """Return the LOCATION header fields as a dict."""
    location = _read_lines(Path(path))[0]
    keys = [
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
    return {k: v.strip() for k, v in zip(keys, location.split(",")[1:], strict=False)}


def detect_baseline_year(header_lines: list[str], df: Optional[pd.DataFrame] = None) -> int:
    """Guess the climate baseline year of an EPW file.

    Uses the midpoint of ``Period of Record=YYYY-YYYY`` (TMYx/OneBuilding
    comments). Falls back to the median data year, then raises ``ValueError``.
    """
    for line in header_lines:
        m = _PERIOD_RE.search(line)
        if m:
            start, end = int(m.group(1)), int(m.group(2))
            return round((start + end) / 2)
    if df is not None and "year" in df and df["year"].notna().any():
        return int(df["year"].median())
    raise ValueError("Cannot detect baseline year; pass it explicitly.")
