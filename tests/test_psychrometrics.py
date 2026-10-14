"""Tests for epwupgrader.psychrometrics."""

import math

import numpy as np
import pytest

from epwupgrader.psychrometrics import (
    dew_point_from_rh,
    dew_point_from_vapour_pressure,
    enthalpy,
    humidity_ratio,
    recalculate_dew_point_after_temp_shift,
    recalculate_rh_after_temp_shift,
    rh_from_dew_point,
    rh_from_vapour_pressures,
    saturation_vapour_pressure,
    scale_rh_for_temp_shift,
    vapour_pressure_from_dew_point,
    vapour_pressure_from_rh,
    wet_bulb_temperature,
)


class TestSaturationVapourPressure:
    def test_at_zero_celsius(self):
        result = saturation_vapour_pressure(0.0)
        assert 600.0 < result < 620.0

    def test_at_100_celsius(self):
        result = saturation_vapour_pressure(100.0)
        assert 95000.0 < result < 106000.0

    def test_increases_with_temperature(self):
        temps = [-20.0, 0.0, 20.0, 40.0]
        pressures = [saturation_vapour_pressure(t) for t in temps]
        assert pressures == sorted(pressures)

    def test_negative_temperature(self):
        result = saturation_vapour_pressure(-10.0)
        assert result > 0.0
        assert result < saturation_vapour_pressure(0.0)


class TestVapourPressureFromRH:
    def test_rh_100_equals_saturation(self):
        t = 20.0
        assert vapour_pressure_from_rh(t, 100.0) == pytest.approx(
            saturation_vapour_pressure(t), rel=1e-6
        )

    def test_rh_0_gives_zero(self):
        assert vapour_pressure_from_rh(20.0, 0.0) == pytest.approx(0.0, abs=1e-9)

    def test_rh_50(self):
        t = 20.0
        result = vapour_pressure_from_rh(t, 50.0)
        expected = 0.5 * saturation_vapour_pressure(t)
        assert result == pytest.approx(expected, rel=1e-6)

    def test_rh_clamped_above_100(self):
        t = 20.0
        assert vapour_pressure_from_rh(t, 110.0) == pytest.approx(
            vapour_pressure_from_rh(t, 100.0), rel=1e-6
        )

    def test_rh_clamped_below_0(self):
        assert vapour_pressure_from_rh(20.0, -5.0) == pytest.approx(0.0, abs=1e-9)


class TestDewPointFromRH:
    def test_rh_100_dew_point_equals_dry_bulb(self):
        t = 20.0
        dp = dew_point_from_rh(t, 100.0)
        assert dp == pytest.approx(t, abs=0.1)

    def test_rh_0_returns_lower_bound(self):
        dp = dew_point_from_rh(20.0, 0.0)
        assert dp == pytest.approx(-80.0, abs=1e-6)

    def test_typical_values(self):
        dp = dew_point_from_rh(25.0, 60.0)
        assert 14.0 < dp < 20.0

    def test_dew_point_below_dry_bulb(self):
        for t in [-10.0, 0.0, 15.0, 30.0]:
            for rh in [10.0, 50.0, 90.0]:
                dp = dew_point_from_rh(t, rh)
                assert dp <= t + 1e-6

    def test_roundtrip_with_vapour_pressure(self):
        t = 20.0
        rh = 55.0
        e = vapour_pressure_from_rh(t, rh)
        dp = dew_point_from_vapour_pressure(e)
        e_back = vapour_pressure_from_dew_point(dp)
        assert e_back == pytest.approx(e, rel=1e-4)


class TestDewPointFromVapourPressure:
    def test_non_positive_input_returns_lower_bound(self):
        assert dew_point_from_vapour_pressure(0.0) == pytest.approx(-80.0)
        assert dew_point_from_vapour_pressure(-1.0) == pytest.approx(-80.0)

    def test_roundtrip(self):
        for t in [-10.0, 0.0, 10.0, 20.0, 30.0]:
            e_sat = saturation_vapour_pressure(t)
            t_back = dew_point_from_vapour_pressure(e_sat)
            assert t_back == pytest.approx(t, abs=0.05)


class TestRHFromVapourPressures:
    def test_equal_pressures_gives_100(self):
        assert rh_from_vapour_pressures(1000.0, 1000.0) == pytest.approx(100.0)

    def test_zero_actual_gives_0(self):
        assert rh_from_vapour_pressures(0.0, 1000.0) == pytest.approx(0.0)

    def test_clamped_to_100(self):
        assert rh_from_vapour_pressures(2000.0, 1000.0) == pytest.approx(100.0)

    def test_zero_sat_gives_0(self):
        assert rh_from_vapour_pressures(500.0, 0.0) == pytest.approx(0.0)


class TestRHFromDewPoint:
    def test_equal_temperatures_gives_100(self):
        rh = rh_from_dew_point(20.0, 20.0)
        assert rh == pytest.approx(100.0, abs=0.01)

    def test_dew_point_below_dry_bulb(self):
        rh = rh_from_dew_point(25.0, 10.0)
        assert 0.0 < rh < 100.0

    def test_known_value(self):
        rh = rh_from_dew_point(20.0, 9.3)
        assert 49.0 < rh < 51.0


class TestWetBulbTemperature:
    def test_rh_100_returns_dry_bulb(self):
        wb = wet_bulb_temperature(25.0, 100.0)
        assert wb == pytest.approx(25.0, abs=0.01)

    def test_wet_bulb_less_than_dry_bulb(self):
        for t in [0.0, 10.0, 20.0, 30.0, 40.0]:
            for rh in [20.0, 50.0, 80.0]:
                wb = wet_bulb_temperature(t, rh)
                assert wb <= t + 1e-3

    def test_wet_bulb_above_dew_point(self):
        t, rh = 25.0, 50.0
        dp = dew_point_from_rh(t, rh)
        wb = wet_bulb_temperature(t, rh)
        assert wb >= dp - 0.1

    def test_rh_0_returns_without_error(self):
        wb = wet_bulb_temperature(20.0, 0.0)
        assert isinstance(wb, float)
        assert not math.isnan(wb)

    def test_typical_value(self):
        wb = wet_bulb_temperature(30.0, 50.0)
        assert 20.0 < wb < 30.0


class TestHumidityRatio:
    def test_positive_result(self):
        w = humidity_ratio(20.0, 50.0)
        assert w > 0.0

    def test_increases_with_rh(self):
        w1 = humidity_ratio(20.0, 30.0)
        w2 = humidity_ratio(20.0, 60.0)
        assert w2 > w1

    def test_increases_with_temperature(self):
        w1 = humidity_ratio(10.0, 50.0)
        w2 = humidity_ratio(30.0, 50.0)
        assert w2 > w1


class TestEnthalpy:
    def test_positive_at_typical_conditions(self):
        h = enthalpy(20.0, 50.0)
        assert h > 0.0

    def test_increases_with_temperature(self):
        h1 = enthalpy(10.0, 50.0)
        h2 = enthalpy(30.0, 50.0)
        assert h2 > h1

    def test_known_approx_value(self):
        h = enthalpy(20.0, 50.0)
        assert 35.0 < h < 50.0


class TestRecalculateRHAfterTempShift:
    def test_higher_temp_lowers_rh(self):
        odp = np.array([10.0, 10.0, 10.0])
        new_t = np.array([25.0, 30.0, 35.0])
        rh = recalculate_rh_after_temp_shift(odp, new_t)
        assert all(rh[i] >= rh[i + 1] for i in range(len(rh) - 1))

    def test_clamped_to_0_100(self):
        odp = np.array([-50.0, 5.0])
        new_t = np.array([50.0, 5.0])
        rh = recalculate_rh_after_temp_shift(odp, new_t)
        assert np.all(rh >= 0.0)
        assert np.all(rh <= 100.0)

    def test_same_temp_gives_100_rh(self):
        t = np.array([20.0, 20.0])
        rh = recalculate_rh_after_temp_shift(t, t)
        assert np.allclose(rh, 100.0, atol=0.01)

    def test_returns_numpy_array(self):
        odp = np.array([5.0])
        new_t = np.array([20.0])
        result = recalculate_rh_after_temp_shift(odp, new_t)
        assert isinstance(result, np.ndarray)


class TestRecalculateDewPointAfterTempShift:
    def test_dew_point_unchanged_when_temp_rises(self):
        odp = np.array([10.0, 10.0])
        new_t = np.array([25.0, 30.0])
        result = recalculate_dew_point_after_temp_shift(odp, new_t)
        assert np.allclose(result, odp)

    def test_dew_point_clamped_to_new_dry_bulb_when_temp_falls(self):
        odp = np.array([15.0])
        new_t = np.array([10.0])
        result = recalculate_dew_point_after_temp_shift(odp, new_t)
        assert result[0] == pytest.approx(10.0)

    def test_returns_numpy_array(self):
        odp = np.array([5.0])
        new_t = np.array([20.0])
        result = recalculate_dew_point_after_temp_shift(odp, new_t)
        assert isinstance(result, np.ndarray)


class TestScaleRhForTempShift:
    def test_warming_lowers_rh(self):
        rh = scale_rh_for_temp_shift(np.array([80.0]), np.array([20.0]), np.array([22.0]))
        assert rh[0] < 80.0

    def test_matches_dew_point_method_when_consistent(self):
        rh0 = 100.0 * saturation_vapour_pressure(12.0) / saturation_vapour_pressure(20.0)
        new = scale_rh_for_temp_shift(np.array([rh0]), np.array([20.0]), np.array([23.0]))
        expected = recalculate_rh_after_temp_shift(np.array([12.0]), np.array([23.0]))
        assert new[0] == pytest.approx(expected[0], rel=1e-9)

    def test_clipped_to_100(self):
        rh = scale_rh_for_temp_shift(np.array([99.0]), np.array([20.0]), np.array([10.0]))
        assert rh[0] == 100.0
