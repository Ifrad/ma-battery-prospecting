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
        rows["with_connected_solutions"]["value_per_block"]["p50"]
        >= rows["demand_savings"]["value_per_block"]["p50"]
    )


def test_stream_shares_sum_to_one_and_demand_only_has_no_grid_share():
    rows = {r["scenario"]: r for r in score.score_site(SITE, BUILDINGS, CFG)}
    both = rows["with_connected_solutions"]["streams"]
    assert sum(v["share"] for v in both.values()) == pytest.approx(1.0)
    assert both["connected_solutions"]["p50"] > 0
    alone = rows["demand_savings"]["streams"]
    assert alone["connected_solutions"]["share"] == 0


def test_eversource_sites_are_flagged_rate_area_unconfirmed():
    site = {**SITE, "utility": score.EVERSOURCE}
    x = {"capped": np.zeros(10, dtype=bool)}
    assert "rate_area_unconfirmed" in score.flags(site, x)
    assert score.flags(SITE, {"capped": np.ones(10, dtype=bool)})[-1] == "capped"


def test_ranking_breaks_ties_by_blocks_then_total():
    from prospect.model import report

    rows = [
        {"site_id": "a", "value_p50": 1.0, "blocks": 1.0, "total_p50": 1.0},
        {"site_id": "b", "value_p50": 1.0, "blocks": 2.0, "total_p50": 2.0},
        {"site_id": "c", "value_p50": 1.0, "blocks": 2.0, "total_p50": 3.0},
        {"site_id": "d", "value_p50": 2.0, "blocks": 1.0, "total_p50": 2.0},
    ]
    assert [r["site_id"] for r in sorted(rows, key=report.rank_key)] == [
        "d",
        "c",
        "b",
        "a",
    ]
