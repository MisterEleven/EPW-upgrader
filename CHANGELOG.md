# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [0.1.0] - 2025-07-11

### Added

#### EPW Parsing (`parser.py`)
- `parse_epw(path)` — reads an EnergyPlus Weather (EPW) file and returns a
  `tuple[list[str], pd.DataFrame]`.  The first element contains the 8 raw header
  lines (stripped of trailing newlines); the second is a pandas DataFrame with all
  35 columns defined by `EPW_COLUMNS`, with numeric fields coerced to `float64`
  and `data_flags` left as strings.
- Raises `ValueError` with a descriptive message when the file contains no data
  rows after the header block.
- `parse_epw_meta(path)` — extracts the LOCATION header line and returns a
  `dict[str, str]` with keys `city`, `state`, `country`, `data_type`,
  `wmo_number`, `latitude`, `longitude`, `time_zone`, and `elevation`.
- `write_epw(path, header_lines, df)` — serialises the morphed DataFrame back to a
  valid EPW text file, writing header lines verbatim followed by comma-separated
  data rows in the original EPW column order.  (Also exported from the top-level
  `epwupgrader` namespace via `writer.py`.)
- `EPW_COLUMNS` constant — ordered list of 35 column name strings matching the EPW
  file format specification.
- `NUM_HEADER_LINES = 8` constant.

#### EPW Writing (`writer.py`)
- `write_epw(epw_data, output_path)` — alternative writer accepting a dict with
  keys `"headers"` and `"data"`, as originally produced by the legacy dict-based
  parse API.  Integer columns (`year`, `month`, `day`, `hour`, `minute`) are
  written without a decimal point; all others are formatted to 1 decimal place.
- Raises `OSError` if the output directory does not exist, with a clear message
  instructing the caller to create it before calling `write_epw`.

#### Climate Morphing (`morphing.py`)
- `morph_temperature(df, delta_t, alpha_t=None)` — applies the Belcher *et al.*
  (2005) temperature morphing to the `dry_bulb_temperature` column.  When
  `alpha_t` is `None`, the additive shift-only form is used
  (`T_future = T + delta_t`).  When `alpha_t` is supplied, the combined
  stretch-and-shift form is applied
  (`T_future = T + delta_t + alpha_t * (T - T_monthly_mean)`), where the monthly
  mean is computed per-row via a `groupby` over the `month` column.  After the
  shift, `dew_point_temperature` and `relative_humidity` are immediately
  recalculated to maintain thermodynamic consistency.
- `morph_radiation(df, alpha_ghi, alpha_dni=None, alpha_dhi=None)` — applies
  multiplicative morphing to `global_horiz_radiation`, and optionally to
  `direct_normal_radiation` and `diffuse_horiz_radiation`.  All morphed values are
  floor-clamped to 0 via `numpy.clip`.  Missing columns are skipped with a
  `logging.WARNING` rather than raising an exception.
- `morph_wind_speed(df, alpha_ws)` — applies multiplicative morphing to
  `wind_speed` and clips results to ≥ 0.
- `morph_pressure(df, delta_p)` — applies an additive shift to
  `atmospheric_pressure`.
- `apply_all_morphing(df, deltas, alphas=None)` — convenience wrapper that
  dispatches to `morph_temperature`, `morph_pressure`, `morph_radiation`, and
  `morph_wind_speed` based on the keys present in the `deltas` and `alphas`
  mappings.  Recognised keys match the `COL_*` string constants in `morphing.py`.
- `apply_temperature_morphing(temperature, delta_t, alpha, t_mean)` — scalar
  helper implementing `T + delta_t + 0.5 * alpha * (T - t_mean)`.
- `apply_wind_morphing(wind_speed, scale_factor)` — scalar helper clamped to ≥ 0.
- `apply_precipitation_morphing(precipitation, scale_factor)` — scalar helper
  clamped to ≥ 0.
- Internal helper `_resolve_delta(delta, df)` — accepts a scalar, a length-12
  monthly array (expanded hourly via the `month` column), or a full-length array.
- Internal helper `_monthly_means(df, col)` — returns per-row monthly means using
  `groupby.transform("mean")`.

#### Psychrometric Recalculation (`psychrometrics.py`)
- `saturation_vapor_pressure(temp_c)` — returns saturation vapour pressure in
  Pascals using the Buck (1981) equation with constants E₀ = 611.2 Pa,
  A = 17.368, B = 238.88 °C:
  `611.2 * exp(17.368 * T / (238.88 + T))`.  Vectorised; accepts numpy arrays.
- `recalculate_rh_after_temp_shift(original_dew_point_array, new_dry_bulb_array)`
  — recomputes relative humidity [%] after a dry-bulb temperature change, holding
  actual vapour pressure (derived from the original dew-point) constant.  Output
  is clipped to [0, 100].
- `recalculate_dew_point_after_temp_shift(original_dew_point_array,
  new_dry_bulb_array)` — returns a new dew-point array clipped so that dew-point
  never exceeds dry-bulb: `numpy.minimum(original_dew_point, new_dry_bulb)`.
- `dew_point_from_rh(dry_bulb_c, rh_pct)` — converts dry-bulb temperature and
  relative humidity to dew-point temperature using the inverse Buck equation.
- `rh_from_dew_point(dry_bulb_c, dew_point_c)` — converts dry-bulb and dew-point
  temperatures to relative humidity [%].
- `recalculate_moisture(original_dew_point_array, new_dry_bulb_array)` —
  convenience wrapper returning `(rh_array, dew_point_array)` as a tuple.

#### GCM Anomaly Data — `anomalies.py` (primary)
- `get_monthly_anomalies(scenario, target_year, baseline_year=1980)` — returns a
  `dict[int, dict[str, float]]` mapping month integers 1–12 to per-variable
  anomaly values linearly interpolated to `target_year`.  Supported variables:
  `delta_temp_c`, `alpha_solar`, `beta_wind`, `tail_amplification_factor`.
- Anchor points stored at years 2025, 2050, 2075, and 2100 allow non-linear
  interpolation between decades.
- Raises `ValueError` if `target_year` is outside [2025, 2100] or if `scenario`
  is unrecognised.
- Built-in anomaly tables for **SSP5-8.5** — `delta_temp_c` ranges from
  0.9 + (month−1)×0.02 °C at 2025 to 5.0 + (month−1)×0.08 °C at 2100;
  `tail_amplification_factor` ranges from 1.05 (2025) to 1.50 (2100).
- Built-in anomaly tables for **SSP2-4.5** — `delta_temp_c` ranges from
  0.7 + (month−1)×0.01 °C at 2025 to 2.1 + (month−1)×0.03 °C at 2100;
  `tail_amplification_factor` ranges from 1.02 (2025) to 1.14 (2100).
- Scenario alias resolution (`_SCENARIO_ALIASES`) maps lower-case aliases such as
  `"ssp585"`, `"rcp8.5"`, `"ssp245"`, `"rcp4.5"` to their canonical names.

#### GCM Data Layer (`gcm_data.py`)
- `get_monthly_anomalies(scenario, target_year, baseline_year)` — alternative
  implementation using two flat reference tables (`SSP585_2050` and `SSP245_2100`)
  and a single linear scale factor
  `scale = (target_year − baseline_year) / (2100 − baseline_year)`.  Additive
  fields scaled directly; multiplicative fields interpolated as
  `1.0 + (ref − 1.0) * scale`.  `tail_amplification_factor` is treated as a fixed
  scenario property (not time-interpolated).
- `SSP585_2050` dict — reference end-of-century table for SSP5-8.5; all months
  have `tail_amplification_factor = 1.5`.
- `SSP245_2100` dict — reference end-of-century table for SSP2-4.5; all months
  have `tail_amplification_factor = 1.2`.

#### Command-Line Interface (`cli.py`)
- `epwupgrader INPUT_EPW OUTPUT_EPW` — positional Click arguments.
- `--scenario` option (default `SSP5-8.5`) — climate scenario string passed to
  `get_monthly_anomalies`.
- `--target-year` option (default `2050`) — integer target year.
- `--baseline-year` option (default `1980`) — integer baseline year.
- `--verbose` flag — sets log level to `DEBUG`; otherwise `INFO`.
- Validates that the input file exists before proceeding and exits with code 1
  with an error message if it does not.
- Prints `"Done. Morphed EPW written to {output_epw}"` on successful completion.
- Registered as the `epwupgrader` console script entry point via `setup.py`.

#### Package Exports (`__init__.py`)
- Top-level `epwupgrader` namespace exports:
  `parse_epw`, `write_epw`, `morph_temperature`, `morph_radiation`,
  `morph_wind_speed`, `apply_all_morphing`, `saturation_vapor_pressure`,
  `recalculate_rh_after_temp_shift`, `recalculate_dew_point_after_temp_shift`,
  `get_monthly_anomalies`.
- `__version__ = "0.1.0"`.

#### Project Infrastructure
- `setup.py` with `install_requires = ["pandas>=1.3", "numpy>=1.21"]` and
  `extras_require["dev"]` including `pytest`, `pytest-cov`, and `flake8`.
- `setup.cfg` with `[flake8]` configuration:
  `max-line-length = 100`, `extend-ignore = E203, W503`.
- Test suite in `tests/` covering `anomalies`, `morphing`, `parser`, and
  `psychrometrics` modules.

---

[Unreleased]: https://github.com/example/epwupgrader/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/example/epwupgrader/releases/tag/v0.1.0