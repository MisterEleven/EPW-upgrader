# This file is retained for backwards compatibility only.
# All functionality has moved to epwupgrader.parser.
# Do not import from this module in new code.
from epwupgrader.parser import (  # noqa: F401
    parse_epw,
    parse_epw_meta,
    write_epw,
    EPW_COLUMNS,
    NUM_HEADER_LINES,
)