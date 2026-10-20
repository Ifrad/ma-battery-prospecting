import copy

import numpy as np
import pytest

from prospect.model import grid
from prospect.priors import config

CFG = config.load()
NG = {"utility": "National Grid (Massachusetts Electric)", "profile": "Warehouse"}
PERF, KEEP = 0.61, 1 - 0.13  # performance factor, and the share left by overlap
EXPORT = copy.deepcopy(CFG)
EXPORT["connected_solutions"]["site_exports"]["value"] = True


def ratio(name, profile="Warehouse"):
    return grid.event_ratios({"profile": profile}, CFG)[name]


def test_without_export_the_count_is_capped_by_event_window_load():
    load = ratio("mean_over_peak") * 400.0  # well under 250 x 0.61 = 152.5 kW
    out = grid.grid_revenue(NG, np.full(3, 400.0), 1, CFG)
    assert out["grid_kw"] == pytest.approx([min(250 * PERF, load) * KEEP] * 3)
    assert out["grid_usd"] == pytest.approx(out["grid_kw"] * 200)


def test_a_large_building_is_limited_by_block_output_not_load():
    out = grid.grid_revenue(NG, np.array([5000.0]), 1, CFG)
    assert out["grid_kw"][0] == pytest.approx(250 * PERF * KEEP)


def test_no_open_profile_takes_the_pooled_ratio():
    pooled = CFG["simulation"]["pooled"]["event_window"]["mean_over_peak"]["median"]
    assert ratio("mean_over_peak", "no open profile") == pooled


def test_with_export_a_100_kw_site_counts_at_most_150_kw():
    out = grid.grid_revenue(NG, np.array([100.0]), 1, EXPORT)
    assert out["grid_kw"][0] == pytest.approx(150 * PERF * KEEP)


def test_with_export_a_site_at_167_kw_or_more_is_uncapped():
    out = grid.grid_revenue(NG, np.array([167.0, 1000.0]), 1, EXPORT)
    assert out["grid_kw"] == pytest.approx([250 * PERF * KEEP] * 2, rel=1e-3)


def test_with_export_g3_sites_cap_on_the_window_peak():
    peak = 150.0
    g2 = grid.grid_revenue(NG, np.array([peak]), 1, EXPORT, g3_weight=0.0)
    g3 = grid.grid_revenue(NG, np.array([peak]), 1, EXPORT, g3_weight=1.0)
    window = min(250, 1.5 * peak * ratio("peak_over_peak"))
    assert g3["grid_kw"][0] == pytest.approx(window * PERF * KEEP)
    assert g3["grid_kw"][0] <= g2["grid_kw"][0]


def test_municipal_sites_get_none():
    for utility in (
        "Holden Municipal Light Department",
        "West Boylston Municipal Lighting Plant",
    ):
        out = grid.grid_revenue({"utility": utility}, np.full(3, 400.0), 1, CFG)
        assert out["grid_usd"].max() == 0 and out["grid_kw"].max() == 0
