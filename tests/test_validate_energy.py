import numpy as np
import pytest

from prospect.validate import energy


def rows(towns, segments, areas, kwh):
    return {
        "town": np.array(towns),
        "segment": np.array(segments, dtype=object),
        "area": np.array(areas, dtype=float),
        "kwh": np.array(kwh, dtype=float),
    }


def test_a_towns_own_buildings_never_set_its_estimate():
    r = rows([1, 1, 2, 2], ["a"] * 4, [10, 10, 10, 10], [100, 100, 50, 50])
    est = energy.holdout(r, energy.own_prior)
    # Town 1 is estimated from town 2 only (5 kWh per sq ft) and back.
    assert est["model"] == pytest.approx([50, 50, 100, 100])
    assert est["size"] == pytest.approx([50, 50, 100, 100])


def test_segment_priors_beat_one_global_median_across_segments():
    r = rows(
        [1, 2, 3, 1, 2, 3],
        ["low", "low", "low", "high", "high", "high"],
        [10] * 6,
        [10, 10, 10, 100, 100, 100],
    )
    est = energy.holdout(r, energy.own_prior)
    m, s = energy.metrics(r["kwh"], est["model"]), energy.metrics(r["kwh"], est["size"])
    assert m["mdape"] == pytest.approx(0.0)
    assert s["mdape"] > m["mdape"]


def test_metrics_of_a_perfect_estimate():
    kwh = np.array([1.0, 2.0, 3.0, 4.0])
    m = energy.metrics(kwh, kwh.copy())
    assert m == {"n": 4, "spearman": pytest.approx(1.0), "mdape": 0.0}
