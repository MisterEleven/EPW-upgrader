"""Tests for epwupgrader.scenarios."""

import pytest

from epwupgrader.scenarios import (
    END_YEAR,
    REFERENCE_YEAR,
    get_monthly_anomalies,
    load_anomalies_csv,
    normalise_scenario,
    to_coefficients,
)


@pytest.mark.parametrize("alias", ["SSP5-8.5", "ssp585", "RCP8.5", " ssp5-8.5 "])
def test_aliases(alias):
    assert normalise_scenario(alias) == "SSP5-8.5"


def test_unknown_scenario():
    with pytest.raises(ValueError, match="Unknown scenario"):
        normalise_scenario("SSP9")


def test_full_period_matches_table():
    a = get_monthly_anomalies("SSP5-8.5", END_YEAR, REFERENCE_YEAR)
    assert a[1]["delta_temp_c"] == pytest.approx(5.8)
    assert a[7]["alpha_solar"] == pytest.approx(1.06)


def test_later_baseline_gets_less_warming():
    early = get_monthly_anomalies("SSP5-8.5", 2050, 1990)
    late = get_monthly_anomalies("SSP5-8.5", 2050, 2018)
    assert all(late[m]["delta_temp_c"] < early[m]["delta_temp_c"] for m in range(1, 13))


def test_additive_over_periods():
    a = get_monthly_anomalies("SSP2-4.5", 2050, 2018)[1]["delta_temp_c"]
    b = get_monthly_anomalies("SSP2-4.5", 2080, 2050)[1]["delta_temp_c"]
    c = get_monthly_anomalies("SSP2-4.5", 2080, 2018)[1]["delta_temp_c"]
    assert a + b == pytest.approx(c)


@pytest.mark.parametrize(("target", "baseline"), [(2018, 2018), (2101, 2018), (2050, 1800)])
def test_invalid_years(target, baseline):
    with pytest.raises(ValueError):
        get_monthly_anomalies("SSP5-8.5", target, baseline)


def _write_csv(path, rows):
    path.write_text("month,delta_temp_c,alpha_solar,beta_wind\n" + "\n".join(rows) + "\n")
    return path


def test_load_csv(tmp_path):
    p = _write_csv(tmp_path / "a.csv", [f"{m},1.5,1.02,0.99" for m in range(1, 13)])
    a = load_anomalies_csv(p)
    assert a[12] == {"delta_temp_c": 1.5, "alpha_solar": 1.02, "beta_wind": 0.99}


@pytest.mark.parametrize(
    "rows",
    [
        [f"{m},1,1,1" for m in range(1, 12)],
        [f"{m},1,1,1" for m in range(1, 13)] + ["1,1,1,1"],
        [f"{m},nan,1,1" for m in range(1, 13)],
        [f"{m},1,-1,1" for m in range(1, 13)],
    ],
)
def test_load_csv_invalid(tmp_path, rows):
    with pytest.raises(ValueError):
        load_anomalies_csv(_write_csv(tmp_path / "a.csv", rows))


def test_load_csv_missing_column(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text("month,delta_temp_c\n1,1\n")
    with pytest.raises(ValueError, match="missing columns"):
        load_anomalies_csv(p)


def test_to_coefficients():
    deltas, alphas = to_coefficients(get_monthly_anomalies("SSP5-8.5", 2050, 2018))
    assert deltas["dry_bulb_temperature"].shape == (12,)
    assert set(alphas) == {
        "global_horizontal_radiation",
        "direct_normal_radiation",
        "diffuse_horizontal_radiation",
        "wind_speed",
    }
