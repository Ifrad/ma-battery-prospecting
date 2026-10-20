from datetime import date, datetime, timedelta

import numpy as np
import pytest

from prospect.priors import simulate as sim

B = {"power_kw": 250.0, "usable_kwh": 469.8, "efficiency": 0.975}


def month(base: float = 100.0, night: float = 50.0, days: int = 30) -> np.ndarray:
    """A month with the base load by day and a lower load from 0:00 to 6:00."""
    day = np.full(96, base)
    day[:24] = night
    return np.tile(day, days)[None, :]


def held(load: np.ndarray, counted: np.ndarray | None = None) -> float:
    counted = np.ones_like(load, dtype=bool) if counted is None else counted
    return float(sim.lowest_peak(load, counted, B)[0])


def test_flat_load_gives_no_reduction():
    assert held(np.full((1, 96 * 30), 100.0)) == pytest.approx(100.0)


def test_day_load_is_shifted_to_the_night():
    # Discharging (100 - T) for 18 h must be recharged in 6 h at (T - 50).
    t = (100 * 18 / 0.975 + 50 * 6 * 0.975) / (18 / 0.975 + 6 * 0.975)
    assert held(month()) == pytest.approx(t, abs=0.01)


def test_short_spike_is_shaved_fully():
    load = month()
    load[0, 600] = 300.0  # one 15-minute step, 200 kW above base
    assert held(load) < 100.0  # the spike is gone and the day load shifted


def test_spike_above_battery_power_is_shaved_by_power_only():
    load = month()
    load[0, 600] = 500.0
    assert held(load) == pytest.approx(250.0, abs=0.01)


def test_long_spike_is_only_partly_shaved():
    short, long = month(), month()
    short[0, 600:604] = 300.0  # 1 hour, from 6:15
    long[0, 600:632] = 300.0  # 8 hours, more energy than the battery holds
    assert held(short) < 100.0
    # 8 hours x (300 - T) must fit in 469.8 x 0.975 kWh delivered.
    assert held(long) == pytest.approx(300 - 469.8 * 0.975 / 8, abs=0.05)


def test_spike_outside_the_counted_steps_is_ignored():
    load = month()
    load[0, 600] = 900.0
    counted = np.ones_like(load, dtype=bool)
    counted[0, 600] = False
    assert held(load, counted) == pytest.approx(held(month()), abs=0.01)


def test_g3_window_holidays_in_2018():
    window = {
        "start": "08:00",
        "end": "21:00",
        "holidays": list(sim.HOLIDAYS),
    }
    days = [datetime(2018, 1, 1) + timedelta(days=d) for d in range(365)]
    off = {
        d.date()
        for d in days
        if d.weekday() < 5 and not sim.peak_window([d.replace(hour=12)], window)[0]
    }
    assert off == {
        date(2018, 1, 1),
        date(2018, 2, 19),
        date(2018, 5, 28),
        date(2018, 7, 4),
        date(2018, 9, 3),
        date(2018, 10, 8),
        date(2018, 11, 12),  # Veterans Day on a Sunday, observed Monday
        date(2018, 11, 22),
        date(2018, 12, 25),
    }
    morning = sim.peak_window(
        [datetime(2018, 3, 6, 7, 45), datetime(2018, 3, 6, 8, 0)], window
    )
    evening = sim.peak_window(
        [datetime(2018, 3, 6, 20, 45), datetime(2018, 3, 6, 21, 0)], window
    )
    assert list(morning) == [False, True]
    assert list(evening) == [True, False]


def test_summary_bins_buildings_and_falls_back_when_a_cell_is_small():
    rows, sample = [], []
    for i in range(12):  # 12 offices around 100 kW, 2 near 600 kW
        peak = 100.0 if i < 10 else 600.0
        sample.append({"bldg_id": i, "building_type": "Office", "sqft": 1000.0})
        for m in range(1, 13):
            rows.append(
                {
                    "bldg_id": i,
                    "annual_kwh": peak * 8760 / 2,
                    "annual_peak_kw": peak,
                    "month": m,
                    "month_mean_kw": peak / 2,
                    "month_peak_kw": peak,
                    "month_window_peak_kw": peak,
                    "reduction_all_kw": peak * 0.4,
                    "reduction_window_kw": peak * 0.5,
                }
            )
    out = sim.summarize(rows, sample)
    office = out["types"]["Office"]
    small, mid = office["bins"]["under_200"], office["bins"]["500_to_1000"]
    assert small["buildings"] == 10 and not small["pooled_fallback"]
    assert small["all_hours"]["median"] == pytest.approx(0.4)
    assert mid["buildings"] == 2 and mid["pooled_fallback"]
    assert mid["peak_window"] == out["pooled"]["bins"]["500_to_1000"]["peak_window"]
    assert office["load_factor"]["median"] == pytest.approx(0.5)
    assert office["peak_to_average"]["median"] == pytest.approx(2.0)
