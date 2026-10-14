"""Command-line interface."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import click
from click.core import ParameterSource

from epwupgrader import __version__
from epwupgrader.anomalies import check_physical_bounds, summarise_anomalies
from epwupgrader.morphing import apply_all_morphing
from epwupgrader.parser import detect_baseline_year, parse_epw
from epwupgrader.scenarios import (
    REFERENCE_YEAR,
    SCENARIOS,
    get_monthly_anomalies,
    load_anomalies_csv,
    normalise_scenario,
    to_coefficients,
)
from epwupgrader.writer import annotate_header, write_epw

logger = logging.getLogger("epwupgrader")


@click.command()
@click.argument("input_epw", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("output_epw", type=click.Path(dir_okay=False, path_type=Path))
@click.option(
    "--scenario",
    "-s",
    default="SSP5-8.5",
    show_default=True,
    help=f"Emission scenario: {', '.join(SCENARIOS)} (aliases like ssp585, rcp8.5 work).",
)
@click.option("--target-year", "-y", type=int, default=2050, show_default=True)
@click.option(
    "--baseline-year",
    "-b",
    type=int,
    default=None,
    help="Climate baseline of the input [default: auto-detect].",
)
@click.option(
    "--anomalies",
    "anomalies_csv",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="CSV of monthly factors (overrides --scenario/--target-year).",
)
@click.option("--force", "-f", is_flag=True, help="Overwrite OUTPUT_EPW if it exists.")
@click.option("--verbose", "-v", is_flag=True, help="Verbose logging.")
@click.version_option(__version__, prog_name="epwupgrader")
def main(
    input_epw: Path,
    output_epw: Path,
    scenario: str,
    target_year: int,
    baseline_year: Optional[int],
    anomalies_csv: Optional[Path],
    force: bool,
    verbose: bool,
) -> None:
    """Morph INPUT_EPW to a future climate and write OUTPUT_EPW.

    Example: epwupgrader in.epw out_2050.epw -s SSP5-8.5 -y 2050
    """
    logging.basicConfig(level=logging.DEBUG if verbose else logging.WARNING, format="%(message)s")

    if anomalies_csv:
        ctx = click.get_current_context()
        given = [
            f"--{name.replace('_', '-')}"
            for name in ("scenario", "target_year", "baseline_year")
            if ctx.get_parameter_source(name) is ParameterSource.COMMANDLINE
        ]
        if given:
            raise click.UsageError(f"--anomalies cannot be combined with {', '.join(given)}.")
    if output_epw.resolve() == input_epw.resolve():
        raise click.UsageError("OUTPUT_EPW must differ from INPUT_EPW.")
    if (output_epw.exists() or output_epw.is_symlink()) and not force:
        raise click.UsageError(f"{output_epw} exists; use --force to overwrite.")

    try:
        header_lines, df = parse_epw(input_epw)
        if anomalies_csv:
            anomalies = load_anomalies_csv(anomalies_csv)
            note = f"morphed by epwupgrader {__version__} with {anomalies_csv.name}"
        else:
            if baseline_year is None:
                baseline_year = detect_baseline_year(header_lines, df)
            scenario = normalise_scenario(scenario)
            if baseline_year < REFERENCE_YEAR:
                click.echo(
                    f"warning: baseline {baseline_year} is before the tables' reference year "
                    f"{REFERENCE_YEAR}; changes are extrapolated.",
                    err=True,
                )
            anomalies = get_monthly_anomalies(scenario, target_year, baseline_year)
            note = (
                f"morphed by epwupgrader {__version__}: {scenario} {target_year} "
                f"(baseline {baseline_year})"
            )
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    deltas, alphas = to_coefficients(anomalies)
    morphed = apply_all_morphing(df, deltas=deltas, alphas=alphas)

    flags = {k: v for k, v in summarise_anomalies(check_physical_bounds(morphed)).items() if v}
    for col, count in flags.items():
        click.echo(f"warning: {count} values outside EnergyPlus range: {col}", err=True)

    try:
        write_epw(output_epw, annotate_header(header_lines, note), morphed)
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    before = df["dry_bulb_temperature"].mean()
    after = morphed["dry_bulb_temperature"].mean()
    click.echo(f"{note}")
    click.echo(f"mean dry bulb {before:.2f} -> {after:.2f} degC; wrote {output_epw}")


if __name__ == "__main__":
    main()
