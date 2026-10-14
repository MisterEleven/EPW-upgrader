# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), [SemVer](https://semver.org/).

## [0.2.0] - 2026-10-14

### Added
- Baseline year is auto-detected from `Period of Record=` (TMYx) or the data years.
- `--anomalies` CSV for user-supplied regional factors.
- `--force` flag; the input file and existing outputs (including symlinks) are never overwritten
  silently.
- Input checks: 64 MB size limit, months must be 1–12, and a warning when extra fields are dropped.
- Sub-hourly full-year files are supported.
- The morph settings are recorded in the output's `COMMENTS 2` header.
- Pre-commit hooks (ruff, ruff-format, hygiene checks).
- Release workflow: a `vX.Y.Z` tag builds the wheel and sdist and publishes a GitHub release.

### Fixed
- The package now builds (invalid setuptools backend) and `click` is a declared dependency.
- Empty cells and EnergyPlus missing codes are no longer morphed into fake data.
- Unchanged cells are written back byte-for-byte.
- RH is scaled by `e_s(T)/e_s(T')`, so it can no longer rise under warming.
- The writer no longer corrupts data: weather codes kept their `.0` suffix, AOD and albedo were
  rounded to one decimal, and RH, pressure and radiation were written as floats.
- Interpolation now applies the change from the actual baseline to the target. Before, later
  baselines received too much warming.
- QC bounds used wrong column names, so they never matched.
- `apply_all_morphing` applied dew-point deltas to dry bulb.

### Removed
- Duplicate `gcm_data` tables, compatibility shims, `setup.py`/`setup.cfg`/`requirements.txt`
  and stray agent scripts.
- Documentation of tail amplification, which was never implemented.
- Python 3.9 support.

## [0.1.0] - 2025-07-11

Initial version.
