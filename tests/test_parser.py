"""
Tests for epwupgrader.parser
============================
Tests the public API:
    parse_epw(path) -> (df, metadata, header_lines)
    EPW_COLUMNS      list[str]  (35 field names)
    EPW_HEADER_ROWS  int        (8)
"""

import pandas as pd
import pytest

from epwupgrader.parser import EPW_COLUMNS, EPW_HEADER_ROWS, parse_epw


class TestEPWColumns:
    def test_is_list(self):
        assert isinstance(EPW_COLUMNS, list)

    def test_length(self):
        assert len(EPW_COLUMNS) == 35

    def test_first_field_is_year(self):
        assert EPW_COLUMNS[0] == "year"

    def test_month_field_present(self):
        assert "month" in EPW_COLUMNS

    def test_dry_bulb_temperature_present(self):
        assert "dry_bulb_temperature" in EPW_COLUMNS

    def test_dew_point_temperature_present(self):
        assert "dew_point_temperature" in EPW_COLUMNS

    def test_relative_humidity_present(self):
        assert "relative_humidity" in EPW_COLUMNS

    def test_radiation_fields_present(self):
        assert "global_horiz_radiation" in EPW_COLUMNS
        assert "direct_normal_radiation" in EPW_COLUMNS
        assert "diffuse_horiz_radiation" in EPW_COLUMNS

    def test_wind_speed_present(self):
        assert "wind_speed" in EPW_COLUMNS

    def test_no_duplicates(self):
        assert len(EPW_COLUMNS) == len(set(EPW_COLUMNS))


class TestEPWHeaderRows:
    def test_value_is_eight(self):
        assert EPW_HEADER_ROWS == 8

    def test_is_int(self):
        assert isinstance(EPW_HEADER_ROWS, int)


class TestParseEPWReturnShape:
    def test_returns_three_tuple(self, sample_epw_file):
        result = parse_epw(sample_epw_file)
        assert isinstance(result, tuple) and len(result) == 3

    def test_first_element_is_dataframe(self, sample_epw_file):
        df, _meta, _hdr = parse_epw(sample_epw_file)
        assert isinstance(df, pd.DataFrame)

    def test_second_element_is_dict(self, sample_epw_file):
        _df, meta, _hdr = parse_epw(sample_epw_file)
        assert isinstance(meta, dict)

    def test_third_element_is_list(self, sample_epw_file):
        _df, _meta, hdr = parse_epw(sample_epw_file)
        assert isinstance(hdr, list)


class TestParseEPWDataFrame:
    def test_row_count_is_8760(self, sample_epw_file):
        df, _, _ = parse_epw(sample_epw_file)
        assert len(df) == 8760

    def test_all_epw_columns_present(self, sample_epw_file):
        df, _, _ = parse_epw(sample_epw_file)
        for col in EPW_COLUMNS:
            assert col in df.columns, f"Missing column: {col}"

    def test_month_values_in_range(self, sample_epw_file):
        df, _, _ = parse_epw(sample_epw_file)
        assert df["month"].between(1, 12).all()

    def test_all_12_months_present(self, sample_epw_file):
        df, _, _ = parse_epw(sample_epw_file)
        assert set(df["month"].unique()) == set(range(1, 13))

    def test_dry_bulb_is_numeric(self, sample_epw_file):
        df, _, _ = parse_epw(sample_epw_file)
        assert pd.api.types.is_numeric_dtype(df["dry_bulb_temperature"])

    def test_relative_humidity_in_physical_range(self, sample_epw_file):
        df, _, _ = parse_epw(sample_epw_file)
        assert (df["relative_humidity"] >= 0).all()
        assert (df["relative_humidity"] <= 100).all()

    def test_wind_speed_non_negative(self, sample_epw_file):
        df, _, _ = parse_epw(sample_epw_file)
        assert (df["wind_speed"] >= 0).all()

    def test_solar_radiation_non_negative(self, sample_epw_file):
        df, _, _ = parse_epw(sample_epw_file)
        assert (df["global_horiz_radiation"] >= 0).all()
        assert (df["direct_normal_radiation"] >= 0).all()
        assert (df["diffuse_horiz_radiation"] >= 0).all()

    def test_first_row_month_is_1(self, sample_epw_file):
        df, _, _ = parse_epw(sample_epw_file)
        assert df["month"].iloc[0] == 1

    def test_last_row_month_is_12(self, sample_epw_file):
        df, _, _ = parse_epw(sample_epw_file)
        assert df["month"].iloc[-1] == 12


class TestParseEPWMeta:
    def test_metadata_has_city(self, sample_epw_file):
        _, meta, _ = parse_epw(sample_epw_file)
        assert "city" in meta

    def test_metadata_has_latitude(self, sample_epw_file):
        _, meta, _ = parse_epw(sample_epw_file)
        assert "latitude" in meta

    def test_metadata_has_longitude(self, sample_epw_file):
        _, meta, _ = parse_epw(sample_epw_file)
        assert "longitude" in meta

    def test_metadata_latitude_value(self, sample_epw_file):
        _, meta, _ = parse_epw(sample_epw_file)
        assert meta["latitude"] == pytest.approx(51.5, abs=0.1)

    def test_metadata_city_value(self, sample_epw_file):
        _, meta, _ = parse_epw(sample_epw_file)
        assert meta["city"] == "TestCity"


class TestParseEPWHeaderLines:
    def test_header_lines_count(self, sample_epw_file):
        _, _, hdr = parse_epw(sample_epw_file)
        assert len(hdr) == EPW_HEADER_ROWS

    def test_first_header_starts_with_location(self, sample_epw_file):
        _, _, hdr = parse_epw(sample_epw_file)
        assert hdr[0].startswith("LOCATION")

    def test_header_lines_are_strings(self, sample_epw_file):
        _, _, hdr = parse_epw(sample_epw_file)
        assert all(isinstance(line, str) for line in hdr)


class TestParseEPWErrors:
    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            parse_epw(tmp_path / "nonexistent.epw")

    def test_accepts_string_path(self, sample_epw_file):
        df, _, _ = parse_epw(str(sample_epw_file))
        assert len(df) == 8760