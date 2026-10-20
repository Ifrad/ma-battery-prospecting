import pytest

from prospect.model import grid
from prospect.priors import config

CFG = config.load()


def test_eligible_site_earns_power_times_performance_less_overlap():
    site = {"utility": "National Grid (Massachusetts Electric)"}
    out = grid.grid_revenue(site, 3, CFG)
    kw = 250 * 0.61 * (1 - 0.13)
    assert out["grid_kw"] == pytest.approx([kw] * 3)
    assert out["grid_usd"] == pytest.approx([kw * 200] * 3)


def test_municipal_sites_get_none():
    for utility in (
        "Holden Municipal Light Department",
        "West Boylston Municipal Lighting Plant",
    ):
        out = grid.grid_revenue({"utility": utility}, 3, CFG)
        assert out["grid_usd"].max() == 0 and out["grid_kw"].max() == 0
