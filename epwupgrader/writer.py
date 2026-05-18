"""
EPW file writer.

Serialises a morphed pandas DataFrame back to a valid ``.epw`` text file.
The header lines are written verbatim; data rows are formatted to match
the column precision conventions used by EnergyPlus.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Union

import pandas as pd

from epwupgrader.parser import EPW_COLUMNS

logger = logging.getLogger(__name__)

# Columns that must be written as integers (no decimal point)
_INT_COLS = {"year", "month", "day", "hour", "minute"}

# Solar radiation columns - clipped to >= 0 before writing as a final safety net
_RADIATION_COLS = {
    "global_horizontal_radiation",
    "direct_normal_radiation",
    "diffuse_horizontal_radiation",
    "extraterrestrial_horizontal_radiation",
    "extraterrestrial_direct_normal_radiation",
    "horizontal_infrared_radiation_intensity",
}


def _format_value(col: str, val) -> str:
    """Format a single EPW cell value to the correct string representation.

    EnergyPlus requires integer columns (year/month/day/hour/minute) to
    have no decimal point. All other numeric columns are written with one
    decimal place. The data-source flags column is written as-is.
    """
    if col == "data_flags":
        return str(val)
    if col in _INT_COLS:
        try:
            return str(int(val))
        except (ValueError, TypeError):
            return str(val)
    try:
        return f"{float(val):.1f}"
    except (ValueError, TypeError):
        return str(val)


def write_epw(
    path: Union[str, Path],
    header_lines: List[str],
    df: pd.DataFrame,
) -> None:
    """Write a morphed EPW DataFrame back to a ``.epw`` file on disk.

    The eight header lines are written verbatim (a trailing newline is
    appended if absent).  The 8 760 data rows follow, each formatted as
    35 comma-separated fields matching the EnergyPlus EPW specification.

    Parameters
    ----------
    path:
        Destination file path.  The parent directory must already exist.
    header_lines:
        List of exactly 8 raw header strings, as returned by
        :func:`epwupgrader.parser.parse_epw`.
    df:
        Morphed data DataFrame.  Must contain all columns listed in
        :data:`epwupgrader.parser.EPW_COLUMNS`.

    Raises
    ------
    ValueError
        If *df* does not contain exactly 8 760 rows, or if any required
        column is missing.
    OSError
        If the output file cannot be written.
    """
    path = Path(path)
    logger.debug("Writing EPW file: %s", path)

    # Validate row count
    if len(df) != 8760:
        raise ValueError(
            f"EPW data must contain exactly 8 760 rows, got {len(df)}."
        )

    # Validate columns
    missing = [c for c in EPW_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"DataFrame is missing required EPW columns: {missing}"
        )

    # Final radiation safety clip (defence-in-depth after morphing)
    df = df.copy()
    for col in _RADIATION_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").clip(lower=0)

    with path.open("w", newline="\n", encoding="utf-8") as fh:
        # Write the 8 header lines verbatim
        for line in header_lines:
            fh.write(line if line.endswith("\n") else line + "\n")

        # Write the 8 760 data rows
        for _, row in df.iterrows():
            parts = [_format_value(col, row[col]) for col in EPW_COLUMNS]
            fh.write(",".join(parts) + "\n")

    logger.debug("Wrote %d data rows to %s", len(df), path)


__all__ = ["write_epw"]