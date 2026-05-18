"""Tests for epwupgrader.morphing."""

import numpy as np
import pandas as pd
import pytest

from epwupgrader.morphing import (
    apply_all_morphing,
    morph_radiation,
    morph_temperature,
    morph_wind_speed,
)


class TestMorphTemperature:
    def test_additive_shift_increases_temperature(self, small_epw_df):
        delta = 3.0
        result = morph_temperature(small_epw_df, delta_t=delta)
        orig = small_epw_df["dry_bulb_temperature"].to_numpy()
        morphed = result["dry_bulb_temperature"].to_numpy()
        assert np.allclose(morphed, orig + delta)

    def test_zero_delta_leaves_temperature_unchanged(self, small_epw_df):
        result = morph_temperature(small_epw_df, delta_t=0.0)
        orig = small_epw_df["dry_bulb_temperature"].to_numpy()
        morphed = result["dry_bulb_temperature"].to_numpy()
        assert np.allclose(morphed, orig)

    def test_negative_delta_decreases_temperature(self, small_epw_df):
        result = morph_temperature(small_epw_df, delta_t=-2.0)
        orig = small_epw_df["dry_bulb_temperature"].to_numpy()
        morphed = result["dry_bulb_temperature"].to_numpy()
        assert np.all(morphed < orig)

    def test_rh_decreases_after_positive_shift(self, small_epw_df):
        result = morph_temperature(small_epw_df, delta_t=5.0)
        orig_rh = small_epw_df["relative_humidity"].to_numpy()
        new_rh = result["relative_humidity"].to_numpy()
        assert np.all(new_rh <= orig_rh + 0.01)

    def test_rh_stays_in_valid_range(self, small_epw_df):
        result = morph_temperature(small_epw_df, delta_t=10.0)
        rh = result["relative_humidity"].to_numpy()
        assert np.all(rh >= 0.0)
        assert np.all(rh <= 100.0)

    def test_dew_point_never_exceeds_dry_bulb(self, small_epw_df):
        result = morph_temperature(small_epw_df, delta_t=5.0)
        tdb = result["dry_bulb_temperature"].to_numpy()
        tdp = result["dew_point_temperature"].to_numpy()
        assert np.all(tdp <= tdb + 1e-9)

    def test_returns_dataframe_not_inplace(self, small_epw_df):
        orig_val = small_epw_df["dry_bulb_temperature"].iloc[0]
        result = morph_temperature(small_epw_df, delta_t=2.0)
        assert small_epw_df["dry_bulb_temperature"].iloc[0] == pytest.approx(orig_val)
        assert result["dry_bulb_temperature"].iloc[0] == pytest.approx(orig_val + 2.0)

    def test_per_hour_array_delta(self, small_epw_df):
        n = len(small_epw_df)
        delta_arr = np.full(n, 2.5)
        result = morph_temperature(small_epw_df, delta_t=delta_arr)
        orig = small_epw_df["dry_bulb_temperature"].to_numpy()
        morphed = result["dry_bulb_temperature"].to_numpy()
        assert np.allclose(morphed, orig + 2.5)


class TestMorphRadiation:
    def test_alpha_greater_than_one_increases_ghi(self, small_epw_df):
        result = morph_radiation(small_epw_df, alpha_ghi=1.1)
        orig = small_epw_df["global_horiz_radiation"].to_numpy()
        morphed = result["global_horiz_radiation"].to_numpy()
        assert np.all(morphed >= orig - 1e-9)

    def test_alpha_one_leaves_ghi_unchanged(self, small_epw_df):
        result = morph_radiation(small_epw_df, alpha_ghi=1.0)
        orig = small_epw_df["global_horiz_radiation"].to_numpy()
        morphed = result["global_horiz_radiation"].to_numpy()
        assert np.allclose(morphed, orig)

    def test_radiation_never_goes_negative(self, small_epw_df):
        result = morph_radiation(
            small_epw_df, alpha_ghi=0.5, alpha_dni=0.5, alpha_dhi=0.5
        )
        assert (result["global_horiz_radiation"] >= 0).all()
        assert (result["direct_normal_radiation"] >= 0).all()
        assert (result["diffuse_horiz_radiation"] >= 0).all()

    def test_dni_morphed_independently(self, small_epw_df):
        result = morph_radiation(small_epw_df, alpha_ghi=1.0, alpha_dni=1.2)
        orig_dni = small_epw_df["direct_normal_radiation"].to_numpy()
        morphed_dni = result["direct_normal_radiation"].to_numpy()
        assert np.allclose(morphed_dni, np.clip(orig_dni * 1.2, 0.0, None))

    def test_dhi_morphed_independently(self, small_epw_df):
        result = morph_radiation(small_epw_df, alpha_ghi=1.0, alpha_dhi=0.9)
        orig_dhi = small_epw_df["diffuse_horiz_radiation"].to_numpy()
        morphed_dhi = result["diffuse_horiz_radiation"].to_numpy()
        assert np.allclose(morphed_dhi, np.clip(orig_dhi * 0.9, 0.0, None))

    def test_returns_dataframe(self, small_epw_df):
        result = morph_radiation(small_epw_df, alpha_ghi=1.05)
        assert isinstance(result, pd.DataFrame)

    def test_non_radiation_columns_unchanged(self, small_epw_df):
        result = morph_radiation(small_epw_df, alpha_ghi=1.1)
        orig_t = small_epw_df["dry_bulb_temperature"].to_numpy()
        new_t = result["dry_bulb_temperature"].to_numpy()
        assert np.allclose(orig_t, new_t)


class TestMorphWindSpeed:
    def test_alpha_greater_than_one_increases_wind(self, small_epw_df):
        result = morph_wind_speed(small_epw_df, alpha_ws=1.1)
        orig = small_epw_df["wind_speed"].to_numpy()
        morphed = result["wind_speed"].to_numpy()
        assert np.all(morphed >= orig - 1e-9)

    def test_alpha_one_leaves_wind_unchanged(self, small_epw_df):
        result = morph_wind_speed(small_epw_df, alpha_ws=1.0)
        orig = small_epw_df["wind_speed"].to_numpy()
        morphed = result["wind_speed"].to_numpy()
        assert np.allclose(morphed, orig)

    def test_wind_speed_never_negative(self, small_epw_df):
        result = morph_wind_speed(small_epw_df, alpha_ws=0.0)
        assert (result["wind_speed"] >= 0).all()

    def test_alpha_less_than_one_decreases_wind(self, small_epw_df):
        result = morph_wind_speed(small_epw_df, alpha_ws=0.8)
        orig = small_epw_df["wind_speed"].to_numpy()
        morphed = result["wind_speed"].to_numpy()
        assert np.all(morphed <= orig + 1e-9)

    def test_returns_dataframe(self, small_epw_df):
        result = morph_wind_speed(small_epw_df, alpha_ws=1.05)
        assert isinstance(result, pd.DataFrame)

    def test_non_wind_columns_unchanged(self, small_epw_df):
        result = morph_wind_speed(small_epw_df, alpha_ws=1.2)
        orig_t = small_epw_df["dry_bulb_temperature"].to_numpy()
        new_t = result["dry_bulb_temperature"].to_numpy()
        assert np.allclose(orig_t, new_t)


class TestApplyAllMorphing:
    def test_returns_dataframe(self, small_epw_df):
        deltas = {"dry_bulb_temperature": 2.0}
        result = apply_all_morphing(small_epw_df, deltas=deltas)
        assert isinstance(result, pd.DataFrame)

    def test_temperature_shift_applied(self, small_epw_df):
        deltas = {"dry_bulb_temperature": 3.0}
        result = apply_all_morphing(small_epw_df, deltas=deltas)
        orig = small_epw_df["dry_bulb_temperature"].to_numpy()
        morphed = result["dry_bulb_temperature"].to_numpy()
        assert np.allclose(morphed, orig + 3.0)

    def test_wind_alpha_applied(self, small_epw_df):
        alphas = {"wind_speed": 1.1}
        result = apply_all_morphing(small_epw_df, deltas={}, alphas=alphas)
        orig = small_epw_df["wind_speed"].to_numpy()
        morphed = result["wind_speed"].to_numpy()
        assert np.allclose(morphed, np.clip(orig * 1.1, 0.0, None))

    def test_empty_deltas_and_alphas_returns_copy(self, small_epw_df):
        result = apply_all_morphing(small_epw_df, deltas={})
        orig = small_epw_df["dry_bulb_temperature"].to_numpy()
        new = result["dry_bulb_temperature"].to_numpy()
        assert np.allclose(orig, new)