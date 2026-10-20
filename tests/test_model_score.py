import numpy as np
import pytest

from prospect.model import score
from prospect.priors import config

CFG = config.load()
NG = "National Grid (Massachusetts Electric)"
SITE = {"site_id": "S1", "utility": NG, "profile": "Warehouse"}
BUILDINGS = [
    {
        "building_id": 3,
        "segment": "warehouse",
        "electricity_source": "estimated",
        "grid_kwh": None,
        "lber_confidence": None,
        "area_sqft": 300000.0,
        "area_source": "assessor",
    }
]


def test_two_scenarios_differ_only_by_connected_solutions():
    rows = {r["scenario"]: r for r in score.score_site(SITE, BUILDINGS, CFG)}
    assert set(rows) == {"demand_savings", "with_connected_solutions"}
    a, b = rows["demand_savings"]["draws"], rows["with_connected_solutions"]["draws"]
    assert np.array_equal(a["demand_usd"], b["demand_usd"])
    assert np.allclose(b["value_per_block"] - a["value_per_block"], b["grid_usd"])
    assert (
        rows["with_connected_solutions"]["break_even"]["p50"]
        >= rows["demand_savings"]["break_even"]["p50"]
    )


def test_stream_shares_sum_to_one_and_demand_only_has_no_grid_share():
    rows = {r["scenario"]: r for r in score.score_site(SITE, BUILDINGS, CFG)}
    both = rows["with_connected_solutions"]["streams"]
    assert sum(v["share"] for v in both.values()) == pytest.approx(1.0)
    assert both["connected_solutions"]["p50"] > 0
    alone = rows["demand_savings"]["streams"]
    assert alone["connected_solutions"]["share"] == 0
