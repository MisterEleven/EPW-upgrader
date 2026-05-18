"""
Tests for epwupgrader.anomalies
"""

import numpy as np
import pandas as pd
import pytest

from epwupgrader.anomalies import (
    check_physical_bounds,
    detect_wind_anomalies,
    flag_anomalies,
    summarise_anomalies,
)


def _make_df(n: int = 100, **kwargs) -> pd.DataFrame:
    """Build a small test DataFrame with default numeric columns."""
    base = {
        "dry_bulb_temperature": np.linspace(5.0, 25.0, n),
        "relative_humidity": np.full(n, 60.0),
        "wind_speed": np.full(n, 3.0),
        "wind_direction": np.full(n, 180.0),
    }
    base.update(kwargs)
    return pd.DataFrame(base)


class TestFlagAnomalies:
    def test_returns_dataframe(self):
        df = _make_df()
        result = flag_anomalies(df)
        assert isinstance(result, pd.DataFrame)

    def test_does_not_modify_input(self):
        df = _make_df()
        original_cols = list(df.columns)
        flag_anomalies(df)
        assert list(df.columns) == original_cols

    def test_anomaly_columns_added(self):
        df = _make_df()
        result = flag_anomalies(df, columns=["dry_bulb_temperature"])
        assert "dry_bulb_temperature_anomaly" in result.columns

    def test_anomaly_column_dtype_is_bool(self):
        df = _make_df()
        result = flag_anomalies(df, columns=["dry_bulb_temperature"])
        assert result["dry_bulb_temperature_anomaly"].dtype == bool

    def test_no_anomalies_in_normal_data(self):
        df = _make_df()
        result = flag_anomalies(df, columns=["dry_bulb_temperature"], z_threshold=4.0)
        assert result["dry_bulb_temperature_anomaly"].sum() == 0

    def test_detects_extreme_outlier(self):
        df = _make_df()
        df = df.copy()
        df.loc[50, "dry_bulb_temperature"] = 9999.0
        result = flag_anomalies(df, columns=["dry_bulb_temperature"], z_threshold=3.0)
        assert bool(result.loc[50, "dry_bulb_temperature_anomaly"]) is True

    def test_constant_column_gives_no_anomalies(self):
        df = pd.DataFrame({"val": np.full(50, 5.0)})
        result = flag_anomalies(df, columns=["val"])
        assert result["val_anomaly"].dtype == bool
        assert result["val_anomaly"].sum() == 0

    def test_missing_column_is_skipped(self):
        df = _make_df()
        result = flag_anomalies(df, columns=["nonexistent_col"])
        assert "nonexistent_col_anomaly" not in result.columns

    def test_default_columns_uses_all_numeric(self):
        df = _make_df()
        result = flag_anomalies(df)
        for col in ["dry_bulb_temperature", "relative_humidity",
                    "wind_speed", "wind_direction"]:
            assert f"{col}_anomaly" in result.columns

    def test_multiple_columns(self):
        df = _make_df()
        result = flag_anomalies(df, columns=["dry_bulb_temperature", "relative_humidity"])
        assert "dry_bulb_temperature_anomaly" in result.columns
        assert "relative_humidity_anomaly" in result.columns

    def test_all_anomaly_dtypes_are_bool(self):
        df = _make_df()
        result = flag_anomalies(df)
        anomaly_cols = [c for c in result.columns if c.endswith("_anomaly")]
        for col in anomaly_cols:
            assert result[col].dtype == bool, f"{col} has dtype {result[col].dtype}"

    def test_z_threshold_respected(self):
        vals = np.concatenate([np.full(98, 10.0), [10000.0, 10000.0]])
        df = pd.DataFrame({"temp": vals})
        result_strict = flag_anomalies(df, columns=["temp"], z_threshold=2.0)
        result_loose = flag_anomalies(df, columns=["temp"], z_threshold=100.0)
        assert result_strict["temp_anomaly"].sum() >= result_loose["temp_anomaly"].sum()


class TestCheckPhysicalBounds:
    def test_in_bounds_gives_no_flags(self):
        df = pd.DataFrame({
            "dry_bulb_temperature": [20.0, 15.0, 10.0],
            "relative_humidity": [60.0, 70.0, 50.0],
        })
        result = check_physical_bounds(df)
        assert result["dry_bulb_temperature_out_of_bounds"].sum() == 0
        assert result["relative_humidity_out_of_bounds"].sum() == 0

    def test_out_of_bounds_flagged(self):
        df = pd.DataFrame({
            "dry_bulb_temperature": [100.0, -100.0, 20.0],
        })
        result = check_physical_bounds(df)
        assert result["dry_bulb_temperature_out_of_bounds"].sum() == 2

    def test_out_of_bounds_dtype_is_bool(self):
        df = pd.DataFrame({"wind_speed": [5.0, 200.0, 3.0]})
        result = check_physical_bounds(df)
        assert result["wind_speed_out_of_bounds"].dtype == bool

    def test_missing_column_is_skipped(self):
        df = pd.DataFrame({"nonexistent": [1.0, 2.0]})
        result = check_physical_bounds(df)
        assert "nonexistent_out_of_bounds" not in result.columns

    def test_custom_bounds(self):
        df = pd.DataFrame({"temp": [5.0, 15.0, 25.0]})
        result = check_physical_bounds(df, bounds={"temp": (10.0, 20.0)})
        assert bool(result.loc[0, "temp_out_of_bounds"]) is True
        assert bool(result.loc[1, "temp_out_of_bounds"]) is False
        assert bool(result.loc[2, "temp_out_of_bounds"]) is True


class TestDetectWindAnomalies:
    def test_returns_dataframe(self):
        df = _make_df()
        result = detect_wind_anomalies(df)
        assert isinstance(result, pd.DataFrame)

    def test_expected_columns_added(self):
        df = _make_df()
        result = detect_wind_anomalies(df)
        assert "wind_speed_unphysical" in result.columns
        assert "wind_direction_out_of_range" in result.columns
        assert "wind_calm_direction_inconsistency" in result.columns

    def test_all_flag_dtypes_are_bool(self):
        df = _make_df()
        result = detect_wind_anomalies(df)
        for col in ["wind_speed_unphysical", "wind_direction_out_of_range",
                    "wind_calm_direction_inconsistency"]:
            assert result[col].dtype == bool

    def test_negative_wind_speed_flagged(self):
        df = _make_df()
        df = df.copy()
        df.loc[5, "wind_speed"] = -1.0
        result = detect_wind_anomalies(df)
        assert bool(result.loc[5, "wind_speed_unphysical"]) is True

    def test_normal_wind_speed_not_flagged(self):
        df = _make_df()
        result = detect_wind_anomalies(df)
        assert result["wind_speed_unphysical"].sum() == 0

    def test_direction_out_of_range_flagged(self):
        df = _make_df()
        df = df.copy()
        df.loc[0, "wind_direction"] = 400.0
        df.loc[1, "wind_direction"] = -5.0
        result = detect_wind_anomalies(df)
        assert bool(result.loc[0, "wind_direction_out_of_range"]) is True
        assert bool(result.loc[1, "wind_direction_out_of_range"]) is True

    def test_calm_with_nonzero_direction_flagged(self):
        df = pd.DataFrame({
            "wind_speed": [0.0, 0.3, 0.1],
            "wind_direction": [90.0, 180.0, 0.0],
        })
        result = detect_wind_anomalies(df, calm_threshold=0.5)
        assert bool(result.loc[0, "wind_calm_direction_inconsistency"]) is True
        assert bool(result.loc[1, "wind_calm_direction_inconsistency"]) is True
        assert bool(result.loc[2, "wind_calm_direction_inconsistency"]) is False

    def test_missing_speed_column_does_not_raise(self):
        df = pd.DataFrame({"wind_direction": [180.0, 270.0]})
        result = detect_wind_anomalies(df)
        assert "wind_speed_unphysical" in result.columns
        assert result["wind_speed_unphysical"].sum() == 0

    def test_missing_direction_column_does_not_raise(self):
        df = pd.DataFrame({"wind_speed": [3.0, 5.0]})
        result = detect_wind_anomalies(df)
        assert "wind_direction_out_of_range" in result.columns
        assert result["wind_direction_out_of_range"].sum() == 0


class TestSummariseAnomalies:
    def test_returns_dict(self):
        df = _make_df()
        flagged = flag_anomalies(df, columns=["dry_bulb_temperature"])
        result = summarise_anomalies(flagged)
        assert isinstance(result, dict)

    def test_keys_are_anomaly_columns(self):
        df = _make_df()
        flagged = flag_anomalies(df, columns=["dry_bulb_temperature"])
        result = summarise_anomalies(flagged)
        assert "dry_bulb_temperature_anomaly" in result

    def test_values_are_non_negative_ints(self):
        df = _make_df()
        flagged = flag_anomalies(df)
        result = summarise_anomalies(flagged)
        for v in result.values():
            assert isinstance(v, int)
            assert v >= 0

    def test_count_matches_actual_flags(self):
        vals = np.concatenate([np.full(98, 10.0), [9999.0, 9999.0]])
        df = pd.DataFrame({"temp": vals})
        flagged = flag_anomalies(df, columns=["temp"], z_threshold=3.0)
        result = summarise_anomalies(flagged)
        assert result["temp_anomaly"] == int(flagged["temp_anomaly"].sum())