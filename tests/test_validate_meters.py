from datetime import datetime

import numpy as np
import pytest

from prospect.validate import meters


def test_fifteen_minute_sums_three_readings_and_drops_incomplete(tmp_path):
    path = tmp_path / "1.csv"
    rows = ["timestamp,dttm_utc,value,estimated,anomaly"]
    start = 1341158400  # 2012-07-01 16:00 UTC
    for i, v in enumerate([1, 1, 1, 2, 2, 2, 3]):  # 7 readings: 2 full intervals
        rows.append(f"{start + 300 * (i + 1)},x,{v},0,")
    path.write_text("\n".join(rows) + "\n")
    kw, starts = meters.fifteen_minute(path, "America/New_York")
    assert kw.tolist() == [12.0, 24.0]  # 3 kWh in 15 minutes is 12 kW
    assert starts[0].hour == 12 and starts[0].minute == 0  # 16:00 UTC, EDT


def test_measures_are_unit_free():
    starts = [datetime(2012, 7, 2, h) for h in range(24)] * 1
    kw = np.array([10.0] * 15 + [20.0] * 5 + [10.0] * 4)  # 15 to 20 h at 20
    a = meters.measures(kw, starts)
    b = meters.measures(kw * 37.0, starts)
    assert a["peak_to_average"] == pytest.approx(b["peak_to_average"])
    assert a["load_factor"] == pytest.approx(b["load_factor"])
    assert a["event_mean_over_peak"] == pytest.approx(1.0)


def test_compare_counts_inside_below_above():
    out = meters.compare(
        {m: [0.1, 0.5, 0.9, 0.5] for m in meters.MEASURES},
        {m: (0.2, 0.8) for m in meters.MEASURES},
    )["load_factor"]
    assert (out["inside"], out["below"], out["above"]) == (0.5, 0.25, 0.25)
