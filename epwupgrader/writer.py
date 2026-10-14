"""Write EPW files."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Optional, Sequence, Union

import pandas as pd

from epwupgrader.parser import EPW_COLUMNS, RAW_ATTR, STRING_COLUMNS

# Max decimals per column (trailing zeros are stripped). Unlisted columns are integers.
_DECIMALS = {
    "dry_bulb_temperature": 1,
    "dew_point_temperature": 1,
    "wind_speed": 1,
    "visibility": 1,
    "precipitable_water": 1,
    "aerosol_optical_depth": 4,
    "albedo": 3,
    "liquid_precipitation_depth": 1,
    "liquid_precipitation_quantity": 1,
}

# Full non-leap / leap years, hourly or sub-hourly.
_YEAR_ROWS = (8760, 8784)

# Commas would add CSV fields; control characters (newlines) would add header lines.
_UNSAFE_HEADER_CHARS = re.compile(r"[\x00-\x1f\x7f,]")


def _is_nan(val) -> bool:
    return val is None or (isinstance(val, float) and math.isnan(val))


def _format_value(col: str, val) -> str:
    if col in STRING_COLUMNS:
        return "" if _is_nan(val) else str(val)
    try:
        num = float(val)
    except (TypeError, ValueError):
        return str(val)
    if math.isnan(num):
        return ""
    decimals = _DECIMALS.get(col, 0)
    if decimals == 0:
        return str(int(round(num)))
    text = f"{num:.{decimals}f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def _unchanged(col: str, raw: str, val) -> bool:
    """True if *val* is what the parser read from *raw*."""
    if col in STRING_COLUMNS:
        return raw == ("" if _is_nan(val) else str(val))
    try:
        raw_num = float(raw)
    except ValueError:
        raw_num = math.nan
    num = float(val)
    return raw_num == num or (math.isnan(raw_num) and math.isnan(num))


def _cell(col: str, val, raw: Optional[str]) -> str:
    if raw is not None and _unchanged(col, raw, val):
        return raw
    return _format_value(col, val)


def annotate_header(header_lines: list[str], note: str) -> list[str]:
    """Return a copy of the header with *note* appended to the COMMENTS 2 line."""
    out = list(header_lines)
    for i, line in enumerate(out):
        if line.startswith("COMMENTS 2"):
            out[i] = f"{line},{_UNSAFE_HEADER_CHARS.sub(';', note)}"
            break
    return out


def write_epw(path: Union[str, Path], header_lines: list[str], df: pd.DataFrame) -> None:
    """Write *header_lines* and *df* to an EPW file.

    Cells whose value is unchanged since :func:`parse_epw` keep their original text.
    """
    if not any(len(df) and len(df) % n == 0 for n in _YEAR_ROWS):
        raise ValueError(
            f"EPW data must cover a full year (8760 or 8784 hours), got {len(df)} rows."
        )
    missing = [c for c in EPW_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"DataFrame is missing EPW columns: {missing}")

    raw_rows: Optional[Sequence[Sequence[str]]] = df.attrs.get(RAW_ATTR)
    if raw_rows is not None and len(raw_rows) != len(df):
        raw_rows = None
    no_raw = (None,) * len(EPW_COLUMNS)

    columns = [df[c].tolist() for c in EPW_COLUMNS]
    with Path(path).open("w", newline="\n", encoding="utf-8") as fh:
        for line in header_lines:
            fh.write(line.rstrip("\r\n") + "\n")
        for i, row in enumerate(zip(*columns, strict=True)):
            raw = raw_rows[i] if raw_rows is not None else no_raw
            cells = (_cell(c, v, r) for c, v, r in zip(EPW_COLUMNS, row, raw, strict=True))
            fh.write(",".join(cells) + "\n")
