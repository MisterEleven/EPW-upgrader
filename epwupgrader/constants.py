# This file is retained for backwards compatibility only.
# Column constants have moved to epwupgrader.parser (EPW_COLUMNS)
# and epwupgrader.morphing (COL_* constants).
from epwupgrader.parser import EPW_COLUMNS, NUM_HEADER_LINES  # noqa: F401
from epwupgrader.morphing import (  # noqa: F401
    COL_DRY_BULB,
    COL_DEW_POINT,
    COL_RH,
    COL_PRESSURE,
    COL_GHI,
    COL_DNI,
    COL_DHI,
    COL_WIND_SPEED,
    COL_MONTH,
)