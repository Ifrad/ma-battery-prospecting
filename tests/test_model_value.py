import numpy as np
import pytest

from prospect.model import value
from prospect.priors import config

CFG = config.load()
NG = "National Grid (Massachusetts Electric)"
SITE = {"site_id": "S1", "utility": NG, "profile": "LargeOffice"}
BIG = [
    {
        "building_id": 7,
        "segment": "generic",
        "electricity_source": "measured",
        "grid_kwh": 9_000_000.0,
        "lber_confidence": "high",
        "area_sqft": 400000.0,
        "area_source": "assessor",
    }
]


def test_value_is_demand_plus_grid_and_total_scales_by_blocks():
    x = value.site_draws(SITE, BIG, CFG, ("demand", "connected_solutions"))
    assert x["value_per_block"] == pytest.approx(x["demand_usd"] + x["grid_usd"])
    assert x["total"] == pytest.approx(x["value_per_block"] * x["blocks"])
    s = value.summary(x)
    v = s["value_per_block"]
    assert v["p10"] <= v["p50"] <= v["p90"]
    assert s["blocks"] >= 1


def test_without_connected_solutions_there_is_no_grid_revenue():
    x = value.site_draws(SITE, BIG, CFG, ("demand",))
    assert x["grid_usd"].max() == 0
    assert np.array_equal(x["value_per_block"], x["demand_usd"])
