"""Command-line interface for the EPW upgrader tool."""

from __future__ import annotations

import logging
import sys

import click

from epwupgrader.anomalies import get_monthly_anomalies
from epwupgrader.morphing import apply_all_morphing
from epwupgrader.parser import parse_epw
from epwupgrader.writer import write_epw

logger = logging.getLogger(__name__)


@click.command()
@click.argument("input_epw", type=click.Path(exists=True))
@click.argument("output_epw", type=click.Path())
@click.option(
    "--scenario", "-s",
    default="SSP5-8.5",
    show_default=True,
    help="Climate scenario (SSP5-8.5 or SSP2-4.5).",
)
@click.option(
    "--target-year", "-y",
    default=2050,
    show_default=True,
    type=int,
    help="Target future year for morphing (2025-2100).",
)
@click.option(
    "--baseline-year", "-b",
    default=1980,
    show_default=True,
    type=int,
    help="Baseline year of the source EPW file.",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="Enable verbose logging.",
)
def main(
    input_epw: str,
    output_epw: str,
    scenario: str,
    target_year: int,
    baseline_year: int,
    verbose: bool,
) -> None:
    """Morph INPUT_EPW to a future climate scenario and write OUTPUT_EPW.

    Example:

        epwupgrader baseline.epw future_2050.epw --scenario SSP5-8.5 -y 2050
    """
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    logger.info("Parsing %s", input_epw)
    try:
        header_lines, df = parse_epw(input_epw)
    except Exception as exc:
        click.echo(f"Error reading EPW file: {exc}", err=True)
        sys.exit(1)

    logger.info(
        "Fetching anomalies for %s %d (baseline %d)",
        scenario, target_year, baseline_year,
    )
    try:
        anomalies = get_monthly_anomalies(scenario, target_year, baseline_year)
    except ValueError as exc:
        click.echo(f"Error loading anomalies: {exc}", err=True)
        sys.exit(1)

    # Build deltas and alphas dicts from the anomaly table.
    # Monthly values are stored per month 1-12; _resolve_delta in morphing.py
    # expands them to 8760 hourly values using the DataFrame month column.
    import numpy as np
    months = df["month"].to_numpy(dtype=int)

    delta_t = np.array(
        [anomalies[m]["delta_temp_c"] for m in months], dtype=float
    )
    alpha_solar = np.array(
        [anomalies[m]["alpha_solar"] for m in months], dtype=float
    )
    alpha_wind = np.array(
        [anomalies[m]["beta_wind"] for m in months], dtype=float
    )

    deltas = {"dry_bulb_temperature": delta_t}
    alphas = {
        "global_horizontal_radiation": alpha_solar,
        "direct_normal_radiation": alpha_solar,
        "diffuse_horizontal_radiation": alpha_solar,
        "wind_speed": alpha_wind,
    }

    logger.info("Applying morphing")
    try:
        df_morphed = apply_all_morphing(df, deltas=deltas, alphas=alphas)
    except Exception as exc:
        click.echo(f"Error during morphing: {exc}", err=True)
        sys.exit(1)

    logger.info("Writing %s", output_epw)
    try:
        write_epw(output_epw, header_lines, df_morphed)
    except Exception as exc:
        click.echo(f"Error writing EPW file: {exc}", err=True)
        sys.exit(1)

    click.echo(f"Done. Morphed EPW written to {output_epw}")


if __name__ == "__main__":
    main()