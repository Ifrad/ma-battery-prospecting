import numpy as np
import pytest

from prospect.model import grid
from prospect.priors import config

CFG = config.load()
NG = {"utility": "National Grid (Massachusetts Electric)"}
SCALE = 0.61 * (1 - 0.13)  # performance factor, less the overlap


def test_eligible_site_earns_power_times_performance_less_overlap():
    out = grid.grid_revenue(NG, np.full(3, 400.0), 1, CFG)
    kw = 250 * SCALE
    assert out["grid_kw"] == pytest.approx([kw] * 3)
    assert out["grid_usd"] == pytest.approx([kw * 200] * 3)


def test_a_100_kw_site_counts_at_most_150_kw():
    out = grid.grid_revenue(NG, np.array([100.0]), 1, CFG)
    assert out["grid_kw"][0] == pytest.approx(150 * SCALE)


def test_a_site_at_167_kw_or_more_is_uncapped():
    out = grid.grid_revenue(NG, np.array([167.0, 1000.0]), 1, CFG)
    assert out["grid_kw"] == pytest.approx([250 * SCALE] * 2, rel=1e-3)


def test_municipal_sites_get_none():
    for utility in (
        "Holden Municipal Light Department",
        "West Boylston Municipal Lighting Plant",
    ):
        out = grid.grid_revenue({"utility": utility}, np.full(3, 400.0), 1, CFG)
        assert out["grid_usd"].max() == 0 and out["grid_kw"].max() == 0
