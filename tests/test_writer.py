"""Tests for epwupgrader.writer."""

import pandas as pd
import pytest

from epwupgrader.parser import parse_epw
from epwupgrader.writer import _format_value, annotate_header, write_epw


@pytest.mark.parametrize(
    ("col", "val", "expected"),
    [
        ("year", 2024.0, "2024"),
        ("dry_bulb_temperature", 2.30, "2.3"),
        ("dry_bulb_temperature", -0.04, "0"),
        ("relative_humidity", 83.6, "84"),
        ("aerosol_optical_depth", 0.085, "0.085"),
        ("albedo", 0.11, "0.11"),
        ("visibility", 777.7, "777.7"),
        ("present_weather_codes", "099999999", "099999999"),
        ("data_flags", "?9?9", "?9?9"),
        ("wind_speed", float("nan"), ""),
    ],
)
def test_format_value(col, val, expected):
    assert _format_value(col, val) == expected


def test_roundtrip_is_lossless(full_year_epw_file, tmp_path):
    header, df = parse_epw(full_year_epw_file)
    out = tmp_path / "out.epw"
    write_epw(out, header, df)
    header2, df2 = parse_epw(out)
    assert header2 == header
    assert df2.equals(df)


def test_rejects_wrong_row_count(sample_epw_file, tmp_path):
    header, df = parse_epw(sample_epw_file)
    with pytest.raises(ValueError, match="8760"):
        write_epw(tmp_path / "x.epw", header, df)


def test_rejects_missing_column(full_year_epw_file, tmp_path):
    header, df = parse_epw(full_year_epw_file)
    with pytest.raises(ValueError, match="missing"):
        write_epw(tmp_path / "x.epw", header, df.drop(columns=["albedo"]))


def test_annotate_header():
    header = ["LOCATION,a", "COMMENTS 2,orig"]
    out = annotate_header(header, "morphed, SSP5-8.5")
    assert out[1] == "COMMENTS 2,orig,morphed; SSP5-8.5"
    assert header[1] == "COMMENTS 2,orig"


def test_annotate_header_strips_newlines():
    out = annotate_header(["COMMENTS 2,orig"], "a\nDESIGN CONDITIONS,x\r")
    assert out == ["COMMENTS 2,orig,a;DESIGN CONDITIONS;x;"]


def _raw_lines(path):
    return path.read_text().splitlines()


def test_unchanged_cells_are_verbatim(full_year_epw_file, tmp_path):
    lines = _raw_lines(full_year_epw_file)
    # TMYx-style text: trailing zeros, half-way decimals, missing codes, empty fields.
    lines[8] = (
        "2024,1,1,1,0,?9?9,21.25,-0.30,999,96013,0,0,242,9999,0,0,0,0,0,0,12.5,5.70,"
        "8,8,0.25,376,9,099999999,9,0.0850,1.5,88,0.110,0.25,"
    )
    full_year_epw_file.write_text("\n".join(lines) + "\n")
    header, df = parse_epw(full_year_epw_file)
    out = tmp_path / "out.epw"
    write_epw(out, header, df)
    assert _raw_lines(out) == lines


def test_changed_cells_are_reformatted(full_year_epw_file, tmp_path):
    header, df = parse_epw(full_year_epw_file)
    df.loc[0, "dry_bulb_temperature"] = 12.345
    out = tmp_path / "out.epw"
    write_epw(out, header, df)
    first = _raw_lines(out)[8].split(",")
    assert first[6] == "12.3"
    assert _raw_lines(out)[9:] == _raw_lines(full_year_epw_file)[9:]


def test_sub_hourly_row_count_accepted(full_year_epw_file, tmp_path):
    header, df = parse_epw(full_year_epw_file)
    half_hourly = pd.concat([df, df]).reset_index(drop=True)
    write_epw(tmp_path / "x.epw", header, half_hourly)
