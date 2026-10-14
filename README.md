# epwupgrader

[![CI](https://github.com/MisterEleven/EPW-upgrader/actions/workflows/ci.yml/badge.svg)](https://github.com/MisterEleven/EPW-upgrader/actions/workflows/ci.yml)
[![License: BUSL-1.1](https://img.shields.io/badge/License-BUSL--1.1-blue.svg)](LICENSE)

Morph EnergyPlus weather files (EPW) to a future climate with the Belcher et al. (2005) method.
The hourly pattern of the measured file is kept. Monthly temperature, solar and wind changes are
applied on top of it.

## Install

```bash
pip install https://github.com/MisterEleven/EPW-upgrader/releases/download/v0.2.0/epwupgrader-0.2.0-py3-none-any.whl
# or, from source
pip install -e ".[dev]"
```

## Use

```bash
epwupgrader in.epw out_2050.epw -s SSP5-8.5 -y 2050
```

| Option | Default | |
|---|---|---|
| `-s, --scenario` | `SSP5-8.5` | `SSP5-8.5` or `SSP2-4.5` (aliases `ssp585`, `rcp8.5`, ...) |
| `-y, --target-year` | `2050` | up to 2100 |
| `-b, --baseline-year` | auto | Climate year of the input. Detected from `Period of Record=` (TMYx), else the median data year |
| `--anomalies FILE` | | CSV `month,delta_temp_c,alpha_solar,beta_wind` (12 rows, relative to the input baseline). Overrides `-s` and `-y` |
| `-f, --force` | | Overwrite the output file |

The output header's `COMMENTS 2` line records how the file was morphed.

### Python

```python
from epwupgrader import (
    apply_all_morphing,
    detect_baseline_year,
    get_monthly_anomalies,
    parse_epw,
    to_coefficients,
    write_epw,
)

header, df = parse_epw("in.epw")
anomalies = get_monthly_anomalies("SSP2-4.5", 2070, detect_baseline_year(header, df))
df = apply_all_morphing(df, *to_coefficients(anomalies))
write_epw("out.epw", header, df)
```

## What is changed

| Field | Method |
|---|---|
| Dry bulb | `T + ΔT` (monthly) |
| RH | `RH · e_s(T) / e_s(T′)` (constant vapour pressure) |
| Dew point | unchanged, capped at the new dry bulb |
| GHI, DNI, DHI | `× α_solar`, clipped ≥ 0 |
| Wind speed | `× β_wind`, clipped ≥ 0 |

Everything else is copied verbatim, including design conditions and ground temperatures.
Empty cells and EnergyPlus missing codes (99.9, 999, 9999, ...) are never morphed. Hourly and
sub-hourly full-year files work.

## Limitations

- **The built-in scenario tables are generic, not location-specific.** They are illustrative
  end-of-century changes relative to 1995–2014, interpolated linearly in time. For real studies,
  pass regional factors with `--anomalies` (e.g. [CH2018](https://www.nccs.admin.ch/nccs/en/home/climate-change-and-impacts/swiss-climate-change-scenarios.html) for Switzerland).
- Absolute humidity is held constant, so future RH is probably too low.
- Longwave (infrared) sky radiation, illuminance and precipitation are not morphed.

See [docs/methodology.md](docs/methodology.md) for the equations.

## Development

```bash
pip install -e ".[dev]" && pre-commit install
pytest
```

Releases: bump `__version__` in `epwupgrader/__init__.py`, add a `CHANGELOG.md` section, then push
a tag `vX.Y.Z`. CI builds the wheel and sdist and attaches them to a GitHub release.

## License

[BUSL-1.1](LICENSE)
