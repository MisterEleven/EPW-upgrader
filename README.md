# epwupgrader

**Future-climate EPW morphing for building energy simulation**

[![License: BUSL-1.1](https://img.shields.io/badge/License-BUSL--1.1-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-brightgreen.svg)](https://www.python.org/downloads/)
[![CI](https://img.shields.io/badge/CI-passing-brightgreen.svg)](https://github.com/epwupgrader/epwupgrader/actions)

---

## Overview

`epwupgrader` morphs existing EnergyPlus Weather (EPW) files to represent projected future
climate conditions, enabling building energy simulation under realistic warming scenarios without
replacing observed baseline data entirely.

Rather than substituting raw Global Climate Model (GCM) output — which is too coarse-grained for
building simulation — `epwupgrader` applies the **climate-change morphing** method described in
Belcher et al. (2005). Monthly climate anomalies (delta values) derived from GCM projections are
superimposed on a measured baseline EPW file, preserving the high-frequency variability that
drives peak heating and cooling loads while shifting the climate mean and variance toward a
projected future state.

Supported emission scenarios are **SSP5-8.5** (high emissions) and **SSP2-4.5** (intermediate
emissions), with time-sliced projections from 2020 to 2100. The tool is usable both as a
**command-line interface (CLI)** and as a **Python API**.

---

## Features

- **EPW parsing** — reads all 8 header lines and all 8 760 hourly data rows from any valid EPW
  file into a pandas DataFrame, preserving every original column.
- **EPW writing** — reconstructs a valid EPW file from a morphed DataFrame and the original
  header lines, rounding numeric columns to the same precision used by EnergyPlus.
- **Temperature morphing** — applies Belcher (2005) equations 1 and 3: additive shift (ΔT) on
  dry-bulb temperature with optional diurnal variance scaling (αT); both the *shift-only* and
  *stretch-and-shift* variants are supported.
- **Psychrometric recalculation** — after every dry-bulb temperature shift the dew-point
  temperature and relative humidity are recomputed from the conserved actual vapour pressure
  using the Magnus-Tetens formula (Alduchov & Eskridge 1996 coefficients), keeping moisture
  state physically consistent.
- **Solar radiation morphing** — multiplicative scaling of Global Horizontal Irradiance (GHI,
  column 13), Direct Normal Irradiance (DNI, column 14) and Diffuse Horizontal Irradiance (DHI,
  column 15); results are clipped to ≥ 0 W m⁻².
- **Wind speed morphing** — multiplicative scaling of wind speed (column 21); results are
  clipped to ≥ 0 m s⁻¹.
- **Convenience wrapper** — `apply_all_morphing` applies temperature, radiation and wind speed
  morphing in a single call using a pre-built anomaly dictionary.
- **Built-in GCM anomaly data** — monthly anomaly tables for SSP5-8.5 and SSP2-4.5 derived from
  representative CMIP6 model ensembles, stored in `gcm_data.py`.
- **Temporal interpolation** — linearly interpolates anomalies between a configurable baseline
  year and 2100, so any target year in that range can be requested.
- **Tail amplification** — amplifies extreme (99th-percentile) dry-bulb temperatures by a factor
  of 1.5 when the SSP5-8.5 scenario is selected, reflecting increased frequency of extreme heat
  events.
- **CLI** — `epwupgrader` entry-point with flags for input/output paths, scenario, target year,
  baseline year, and tail-amplification toggle.

---

## Installation

### Standard install (editable)

```bash
git clone https://github.com/epwupgrader/epwupgrader.git
cd epwupgrader
pip install -e .
```

### Development install (includes test and lint dependencies)

```bash
pip install -e ".[dev]"
```

---

## Quick Start — CLI

```
usage: epwupgrader [-h] -i INPUT -o OUTPUT [-s {SSP5-8.5,SSP2-4.5}]
                   [-y TARGET_YEAR] [-b BASELINE_YEAR] [--amplify-tails]
```

| Flag | Default | Description |
|------|---------|-------------|
| `-i`, `--input` | *(required)* | Path to the baseline EPW file |
| `-o`, `--output` | *(required)* | Path for the morphed output EPW file |
| `-s`, `--scenario` | `SSP5-8.5` | Emission scenario (`SSP5-8.5` or `SSP2-4.5`) |
| `-y`, `--target-year` | `2050` | Target projection year (2020–2100) |
| `-b`, `--baseline-year` | `1980` | Baseline year of the input EPW file |
| `--amplify-tails` | off | Amplify 99th-percentile temperature tail (SSP5-8.5 only) |

### Example

```bash
# Morph a London EPW to 2080 under SSP5-8.5 with tail amplification
epwupgrader \
  -i GBR_London.Heathrow.037720_IWEC.epw \
  -o GBR_London.Heathrow.037720_SSP585_2080.epw \
  -s SSP5-8.5 \
  -y 2080 \
  -b 1980 \
  --amplify-tails
```

---

## Quick Start — Python API

```python
from epwupgrader import (
    parse_epw,
    write_epw,
    get_monthly_anomalies,
    morph_temperature,
    morph_radiation,
    morph_wind_speed,
)

# 1. Parse the baseline EPW file
df, metadata, header_lines = parse_epw("GBR_London.Heathrow.037720_IWEC.epw")

# 2. Retrieve monthly anomalies for the chosen scenario and target year
anomalies = get_monthly_anomalies(
    scenario="SSP5-8.5",
    target_year=2060,
    baseline_year=1980,
)

# 3. Apply morphing operations individually

# Temperature: additive shift + optional variance stretch (Belcher eq.1 / eq.3)
df = morph_temperature(df, delta_t=anomalies["delta_t"], alpha_t=anomalies["alpha_t"])

# Radiation: multiplicative stretch for GHI, DNI and DHI
df = morph_radiation(
    df,
    alpha_ghi=anomalies["alpha_ghi"],
    alpha_dni=anomalies["alpha_dni"],
    alpha_dhi=anomalies["alpha_dhi"],
)

# Wind speed: multiplicative stretch
df = morph_wind_speed(df, alpha_ws=anomalies["alpha_ws"])

# 4. Write the morphed EPW
write_epw(df, header_lines, "GBR_London.Heathrow.037720_SSP585_2060.epw")
print("Done.")
```

Or use the single-call convenience wrapper:

```python
from epwupgrader import parse_epw, write_epw, get_monthly_anomalies, apply_all_morphing

df, metadata, header_lines = parse_epw("baseline.epw")
anomalies = get_monthly_anomalies("SSP2-4.5", target_year=2070, baseline_year=1980)
df = apply_all_morphing(df, anomalies)
write_epw(df, header_lines, "future_2070.epw")
```

---

## Methodology

### Temperature — Belcher (2005) equations 1 and 3

**Equation 1 (shift only)**

```
T_future(h) = T_baseline(h) + ΔT_m
```

Where `ΔT_m` is the GCM-projected monthly mean temperature change for month *m*.

**Equation 3 (stretch and shift)**

```
T_future(h) = T_baseline(h) + ΔT_m + αT_m · (T_baseline(h) - T̄_baseline_m)
```

Where `αT_m` is the fractional change in the monthly diurnal temperature range and
`T̄_baseline_m` is the monthly mean of the baseline dry-bulb temperature. When `alpha_t`
is `None` the simpler equation 1 (shift only) is applied.

### Psychrometric Recalculation

After the dry-bulb temperature is shifted, dew-point temperature and relative humidity are
recomputed to keep the **actual vapour pressure** (i.e. the moisture content of the air)
constant. The Magnus-Tetens formula (Alduchov & Eskridge 1996 coefficients) is used to
convert between temperature and saturation vapour pressure:

```
e_s(T) = 6.1078 · exp(17.2694 · T / (T + 237.3))   [hPa, T in °C]
```

The relative humidity is then:

```
RH_new = 100 · e_s(T_dew_original) / e_s(T_dry_new)
```

and is clipped to [0, 100] %.

### Solar Radiation — Multiplicative Stretch

Each irradiance component is multiplied by a monthly scaling factor:

```
GHI_future(h) = αGHI_m · GHI_baseline(h)
DNI_future(h) = αDNI_m · DNI_baseline(h)   (defaults to αGHI if not specified)
DHI_future(h) = αDHI_m · DHI_baseline(h)   (defaults to αGHI if not specified)
```

Results are clipped to ≥ 0 W m⁻² because negative irradiance is non-physical.

### Wind Speed — Multiplicative Stretch

```
WS_future(h) = αWS_m · WS_baseline(h)
```

Results are clipped to ≥ 0 m s⁻¹.

### Tail Amplification

When `--amplify-tails` is active (SSP5-8.5 only), hourly dry-bulb values above the
99th percentile of the morphed series are further amplified by a factor of **1.5**,
capturing the disproportionate increase in extreme heat events projected under high
emissions.

### Temporal Interpolation

Anomaly magnitudes are linearly interpolated between the baseline year and 2100:

```
anomaly(year) = anomaly_2100 · (year - baseline_year) / (2100 - baseline_year)
```

This applies to both additive anomalies (ΔT) and multiplicative anomalies (α).

---

## EPW Format Notes

| Property | Value |
|----------|-------|
| Header lines | 8 (preserved verbatim in output) |
| Data rows | 8 760 (one per hour of a non-leap year) |
| Columns per row | 35 |

**Columns morphed by epwupgrader:**

| Column index | EPW field | Morphing type |
|-------------|-----------|---------------|
| 6 | Dry-bulb temperature (°C) | Additive shift ± variance stretch |
| 7 | Dew-point temperature (°C) | Recalculated from conserved vapour pressure |
| 8 | Relative humidity (%) | Recalculated from conserved vapour pressure |
| 13 | Global Horizontal Irradiance (W m⁻²) | Multiplicative stretch |
| 14 | Direct Normal Irradiance (W m⁻²) | Multiplicative stretch |
| 15 | Diffuse Horizontal Irradiance (W m⁻²) | Multiplicative stretch |
| 21 | Wind speed (m s⁻¹) | Multiplicative stretch |

All other columns (pressure, cloud cover, sky temperature, illuminance values, etc.)
are preserved exactly as read from the baseline EPW.

---

## Project Structure

```
epwupgrader/
├── epwupgrader/
│   ├── __init__.py          # Public API exports
│   ├── anomalies.py         # get_monthly_anomalies, temporal interpolation, tail amplification
│   ├── cli.py               # argparse entry-point
│   ├── gcm_data.py          # GCM_DATA dict: SSP5-8.5 and SSP2-4.5 monthly tables
│   ├── morphing.py          # morph_temperature, morph_radiation, morph_wind_speed,
│   │                        #   apply_all_morphing
│   ├── parser.py            # parse_epw
│   ├── psychrometrics.py    # saturation_vapor_pressure, recalculate_rh_after_temp_shift,
│   │                        #   recalculate_dew_point_after_temp_shift
│   └── writer.py            # write_epw
├── docs/
│   ├── api_reference.md
│   ├── contributing.md
│   └── methodology.md
├── tests/
├── CHANGELOG.md
├── LICENSE
├── README.md
├── requirements.txt
└── setup.py
```

---

## Running Tests

```bash
pytest tests/ -v
```

To run with a short traceback:

```bash
pytest tests/ -v --tb=short
```

---

## Contributing

See [docs/contributing.md](docs/contributing.md) for the full guide, including:

- Development environment setup
- Linting with flake8
- Conventional Commits message format
- How to add a new climate scenario
- How to add a new morphed variable

---

## License

`epwupgrader` is released under the **Business Source License 1.1 (BUSL-1.1)**.

- **Free** for private, academic, and non-commercial use.
- A **commercial license** is required for any for-profit use (e.g. fee-based consultancy,
  SaaS products, or inclusion in commercial software).

For commercial licensing enquiries contact: **license@epwupgrader.io**

See [LICENSE](LICENSE) for the full licence text.

---

## References

1. **Belcher S.E., Hacker J.N. & Powell D.S. (2005).** Constructing design weather data for
   future climates. *Building Services Engineering Research and Technology*, 26(1), 49–61.
   https://doi.org/10.1191/0143624405bt112oa

2. **IPCC (2021).** *Climate Change 2021: The Physical Science Basis. Contribution of Working
   Group I to the Sixth Assessment Report of the Intergovernmental Panel on Climate Change.*
   Cambridge University Press. https://doi.org/10.1017/9781009157896

3. **Alduchov O.A. & Eskridge R.E. (1996).** Improved Magnus Form Approximation of Saturation
   Vapor Pressure. *Journal of Applied Meteorology*, 35(4), 601–609.
   https://doi.org/10.1175/1520-0450(1996)035<0601:IMFAOS>2.0.CO;2