"""Tests for epwupgrader.parser."""

import pandas as pd
import pytest

from epwupgrader.parser import (
    EPW_COLUMNS,
    NUM_HEADER_LINES,
    detect_baseline_year,
    parse_epw,
    parse_epw_meta,
)


def test_columns():
    assert len(EPW_COLUMNS) == 35
    assert len(set(EPW_COLUMNS)) == 35
    assert EPW_COLUMNS[0] == "year"


def test_parse_shape(sample_epw_file):
    header, df = parse_epw(sample_epw_file)
    assert len(header) == NUM_HEADER_LINES
    assert header[0].startswith("LOCATION")
    assert len(df) == 24
    assert list(df.columns) == EPW_COLUMNS


def test_parse_types(sample_epw_file):
    _, df = parse_epw(str(sample_epw_file))
    assert pd.api.types.is_numeric_dtype(df["dry_bulb_temperature"])
    assert df["data_flags"].iloc[0] == "?9?9?9?9?9"
    assert df["present_weather_codes"].iloc[0] == "999999999"


def test_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_epw(tmp_path / "nope.epw")


def test_header_only(tmp_path):
    p = tmp_path / "h.epw"
    p.write_text("LOCATION,x\n" * NUM_HEADER_LINES)
    with pytest.raises(ValueError, match="No data rows"):
        parse_epw(p)


def test_not_epw(tmp_path):
    p = tmp_path / "x.epw"
    p.write_text("foo\n" * 20)
    with pytest.raises(ValueError, match="LOCATION"):
        parse_epw(p)


def test_short_row(sample_epw_file):
    with sample_epw_file.open("a") as fh:
        fh.write("2000,1,2,1,0\n")
    with pytest.raises(ValueError, match="expected 35 fields"):
        parse_epw(sample_epw_file)


def test_latin1(sample_epw_file):
    raw = sample_epw_file.read_bytes().replace(b"TestCity", "Zürich".encode("latin-1"))
    sample_epw_file.write_bytes(raw)
    header, _ = parse_epw(sample_epw_file)
    assert "Zürich" in header[0]


def test_bad_month(sample_epw_file):
    lines = sample_epw_file.read_text().splitlines()
    lines[NUM_HEADER_LINES] = lines[NUM_HEADER_LINES].replace("2000,1,", "2000,13,", 1)
    sample_epw_file.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match="month"):
        parse_epw(sample_epw_file)


def test_meta(sample_epw_file):
    meta = parse_epw_meta(sample_epw_file)
    assert meta["city"] == "TestCity"
    assert float(meta["latitude"]) == pytest.approx(51.5)


def test_baseline_from_period_of_record():
    header = ['COMMENTS 1,"NCEI ISD/ERA5 - Period of Record=2011-2025; Jan=2024"']
    assert detect_baseline_year(header) == 2018


def test_baseline_from_data_years():
    df = pd.DataFrame({"year": [1990, 1995, 2000]})
    assert detect_baseline_year(["COMMENTS 1,none"], df) == 1995


def test_baseline_undetectable():
    with pytest.raises(ValueError):
        detect_baseline_year(["COMMENTS 1,none"])
