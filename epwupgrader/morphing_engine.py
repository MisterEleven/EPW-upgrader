# This file is retained for backwards compatibility only.
# All morphing logic has moved to epwupgrader.morphing.
from epwupgrader.morphing import (  # noqa: F401
    morph_temperature,
    morph_radiation,
    morph_wind_speed,
    morph_pressure,
    apply_all_morphing,
    apply_temperature_morphing,
    apply_wind_morphing,
    apply_precipitation_morphing,
)