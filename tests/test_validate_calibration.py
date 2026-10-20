import pytest

from prospect.validate import calibration


def test_hit_rates_count_inside_below_and_above():
    rows = [
        {"segment": "a", "grid_kwh": 5, "p10": 1, "p90": 10},
        {"segment": "a", "grid_kwh": 0.5, "p10": 1, "p90": 10},
        {"segment": "b", "grid_kwh": 20, "p10": 1, "p90": 10},
        {"segment": "b", "grid_kwh": 10, "p10": 1, "p90": 10},
    ]
    r = calibration.hit_rates(rows)
    assert r["all"] == {"n": 4, "hit": 0.5, "below": 0.25, "above": 0.25}
    assert r["b"]["hit"] == 0.5


def test_holdout_spread_leaves_the_town_out():
    pilot = [
        {"segment": "s", "town_id": 1, "grid_kwh": 1000.0, "area_sqft": 10.0},
        *(
            {"segment": "s", "town_id": 2, "grid_kwh": 10.0 * i, "area_sqft": 10.0}
            for i in (1, 2, 3)
        ),
    ]
    spread = calibration.holdout_spread("s", 1, pilot, healthcare={})
    assert spread["median"] == pytest.approx(2.0)


def test_verdict_uses_the_tolerance():
    assert "not recalibrated" in calibration.verdict({"hit": 0.79}, 0.05)
    assert "need recalibrating" in calibration.verdict({"hit": 0.60}, 0.05)
