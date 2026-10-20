import numpy as np
import pytest

from prospect.model import draws
from prospect.priors import config

CFG = config.load()


def building(bid, **kw):
    b = {
        "building_id": bid,
        "segment": "generic",
        "electricity_source": "estimated",
        "grid_kwh": None,
        "area_sqft": 50000.0,
        "lber_confidence": None,
    }
    return {**b, **kw}


SITE = {"site_id": "S1", "profile": "MediumOffice"}


def test_draws_hit_the_spread():
    z = np.array([-draws.Z90, 0.0, draws.Z90])
    out = draws.from_spread({"p10": 2.0, "median": 5.0, "p90": 20.0}, z)
    assert out == pytest.approx([2.0, 5.0, 20.0])


def test_draws_are_seeded_by_id_not_row_order():
    a = draws.site_draws(SITE, [building(1), building(2)], CFG)
    b = draws.site_draws(SITE, [building(2), building(1)], CFG)
    assert np.array_equal(a["peak_kw"], b["peak_kw"])
    other = draws.site_draws({**SITE, "site_id": "S2"}, [building(1), building(2)], CFG)
    assert not np.array_equal(a["load_factor"], other["load_factor"])


def test_known_kwh_narrows_the_range():
    measured = building(
        1, electricity_source="measured", grid_kwh=2_000_000.0, lber_confidence="high"
    )
    weak = {**measured, "lber_confidence": "ambiguous, 3 buildings"}
    estimated = building(1, area_sqft=2_000_000.0 / 6.54)

    def width(b):
        kwh = draws.site_draws(SITE, [b], CFG)["annual_kwh"]
        return np.percentile(kwh, 90) / np.percentile(kwh, 10)

    assert width(measured) == pytest.approx(1.0)
    assert width(measured) < width(weak)
    assert width(weak) == pytest.approx(width(estimated), rel=0.05)


def test_peak_is_average_load_over_load_factor():
    d = draws.site_draws(SITE, [building(1)], CFG)
    assert d["peak_kw"] == pytest.approx(d["annual_kwh"] / 8760 / d["load_factor"])
    assert ((d["load_factor"] > 0) & (d["load_factor"] <= 1)).all()
