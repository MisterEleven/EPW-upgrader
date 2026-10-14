"""Tests for epwupgrader.cli."""

from click.testing import CliRunner

from epwupgrader.cli import main
from epwupgrader.parser import parse_epw


def test_morph_end_to_end(full_year_epw_file, tmp_path):
    out = tmp_path / "out.epw"
    res = CliRunner().invoke(main, [str(full_year_epw_file), str(out), "-y", "2050"])
    assert res.exit_code == 0, res.output
    assert "baseline 2018" in res.output

    header0, df0 = parse_epw(full_year_epw_file)
    header1, df1 = parse_epw(out)
    assert "SSP5-8.5 2050 (baseline 2018)" in header1[6]
    assert header1[:6] == header0[:6]
    assert (df1["dry_bulb_temperature"] > df0["dry_bulb_temperature"]).all()
    assert df1["dew_point_temperature"].equals(df0["dew_point_temperature"])
    assert df1["relative_humidity"].between(0, 100).all()
    assert df1["present_weather_codes"].equals(df0["present_weather_codes"])
    assert df1["aerosol_optical_depth"].equals(df0["aerosol_optical_depth"])


def test_custom_csv(full_year_epw_file, tmp_path):
    csv = tmp_path / "a.csv"
    csv.write_text(
        "month,delta_temp_c,alpha_solar,beta_wind\n"
        + "\n".join(f"{m},1.0,1.0,1.0" for m in range(1, 13))
    )
    out = tmp_path / "out.epw"
    res = CliRunner().invoke(main, [str(full_year_epw_file), str(out), "--anomalies", str(csv)])
    assert res.exit_code == 0, res.output
    _, df0 = parse_epw(full_year_epw_file)
    _, df1 = parse_epw(out)
    assert (df1["dry_bulb_temperature"] - df0["dry_bulb_temperature"]).round(1).eq(1.0).all()


def test_refuses_overwrite(full_year_epw_file, tmp_path):
    out = tmp_path / "out.epw"
    out.write_text("keep")
    res = CliRunner().invoke(main, [str(full_year_epw_file), str(out)])
    assert res.exit_code != 0
    assert out.read_text() == "keep"


def test_refuses_dangling_symlink(full_year_epw_file, tmp_path):
    out = tmp_path / "out.epw"
    out.symlink_to(tmp_path / "missing_target")
    res = CliRunner().invoke(main, [str(full_year_epw_file), str(out)])
    assert res.exit_code != 0
    assert not (tmp_path / "missing_target").exists()


def test_refuses_same_path(full_year_epw_file):
    res = CliRunner().invoke(main, [str(full_year_epw_file), str(full_year_epw_file), "-f"])
    assert res.exit_code != 0


def test_bad_year_is_clean_error(full_year_epw_file, tmp_path):
    res = CliRunner().invoke(main, [str(full_year_epw_file), str(tmp_path / "o.epw"), "-y", "2200"])
    assert res.exit_code == 1
    assert "Error: target_year" in res.output
    assert "Traceback" not in res.output


def test_scenario_alias(full_year_epw_file, tmp_path):
    res = CliRunner().invoke(
        main, [str(full_year_epw_file), str(tmp_path / "o.epw"), "-s", "ssp245"]
    )
    assert res.exit_code == 0, res.output
    assert "SSP2-4.5" in res.output


def test_anomalies_conflicts_with_year(full_year_epw_file, tmp_path):
    csv = tmp_path / "a.csv"
    csv.write_text("month,delta_temp_c,alpha_solar,beta_wind\n")
    args = [str(full_year_epw_file), str(tmp_path / "o.epw"), "--anomalies", str(csv), "-y", "2080"]
    res = CliRunner().invoke(main, args)
    assert res.exit_code == 2
    assert "--target-year" in res.output


def test_warns_on_extrapolation(full_year_epw_file, tmp_path):
    res = CliRunner().invoke(main, [str(full_year_epw_file), str(tmp_path / "o.epw"), "-b", "1990"])
    assert res.exit_code == 0
    assert "extrapolated" in res.output
