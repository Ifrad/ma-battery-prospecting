import copy

import numpy as np
import pytest

from prospect.model import savings
from prospect.priors import config

CFG = config.load()
NG = savings.NGRID
SITE = {"site_id": "S1", "utility": NG, "profile": "MediumOffice"}


def draws(peak, kwh_month=50_000.0, n=500):
    return {"peak_kw": np.full(n, peak), "annual_kwh": np.full(n, kwh_month * 12)}


def test_blocks_are_one_per_thousand_kw_and_at_least_one():
    assert list(savings.blocks(np.array([150.0, 999.0, 2500.0]), CFG)) == [1, 1, 2]
    capped = copy.deepcopy(CFG)
    capped["model"]["blocks"]["max_blocks"] = 1
    assert list(savings.blocks(np.array([2500.0]), capped)) == [1]


def test_g1_sites_get_no_demand_savings():
    out = savings.demand_savings(SITE, draws(400.0, kwh_month=9_000.0), CFG)
    assert out["demand_usd"].max() == 0


def test_g2_g3_weighting_across_the_band():
    peaks = np.array([100.0, 150.0, 200.0, 250.0, 400.0])
    w2, w3 = savings.schedule_weights(SITE, np.full(5, 50_000.0), peaks, CFG)
    assert list(w3) == [0, 0, 0.5, 1, 1]
    assert list(w2 + w3) == [1, 1, 1, 1, 1]


def test_higher_rate_never_lowers_savings():
    low = savings.demand_savings(SITE, draws(300.0), CFG)
    high_cfg = copy.deepcopy(CFG)
    for s in high_cfg["rates"]["utilities"][NG]["schedules"]:
        s["demand_charge_per_kw_month"] *= 1.5
    high = savings.demand_savings(SITE, draws(300.0), high_cfg)
    assert (high["demand_usd"] >= low["demand_usd"]).all()
    assert high["demand_usd"].sum() > low["demand_usd"].sum()


def test_savings_scale_with_the_realization_factor():
    half = copy.deepcopy(CFG)
    half["profiles"]["realization_factor"]["value"] = 0.4
    full = savings.demand_savings(SITE, draws(300.0), CFG)
    cut = savings.demand_savings(SITE, draws(300.0), half)
    assert cut["demand_usd"] == pytest.approx(full["demand_usd"] / 2)


def test_eversource_uses_g2_all_hours_above_100_kw():
    site = {**SITE, "utility": savings.EVERSOURCE}
    small = savings.demand_savings(site, draws(90.0), CFG)
    big = savings.demand_savings(site, draws(400.0), CFG)
    assert small["demand_usd"].max() == 0
    assert big["kwm_g3"].max() == 0 and big["kwm_g2"].min() > 0
    assert big["demand_usd"] == pytest.approx(big["kwm_g2"] * 33.95)


def test_share_comes_from_the_size_bin_of_the_peak_per_block():
    share = savings.reduction_share(SITE, np.full(4000, 150.0), "all_hours", CFG)
    cell = CFG["simulation"]["types"]["MediumOffice"]["bins"]["under_200"]["all_hours"]
    assert np.median(share) == pytest.approx(cell["median"], rel=0.05)


def test_kw_cut_per_block_never_exceeds_block_power():
    power = CFG["battery"]["block"]["power_kw"]
    real = CFG["profiles"]["realization_factor"]["value"]
    site = {"site_id": "S2", "utility": NG, "profile": "no open profile"}
    out = savings.demand_savings(site, draws(1999.0), CFG)  # one block, 1,999 kW
    monthly = (out["kwm_g2"] + out["kwm_g3"]) / 12
    assert monthly.max() <= power * real + 1e-9


def test_no_profile_share_stays_inside_its_size_bin_range():
    site = {"site_id": "S3", "utility": NG, "profile": "no open profile"}
    low, high = savings.bin_envelope("1000_up", "all_hours", CFG)
    share = savings.reduction_share(site, np.full(500, 1500.0), "all_hours", CFG)
    assert low <= share.min() and share.max() <= high
    small_high = savings.bin_envelope("under_200", "all_hours", CFG)[1]
    assert high < small_high  # large buildings never take a small one's share


def test_capped_marks_draws_whose_cut_reaches_block_power():
    site = {"site_id": "S4", "utility": NG, "profile": "no open profile"}
    big = savings.demand_savings(site, draws(5000.0), CFG)  # one block per 1,000 kW
    small = savings.demand_savings(site, draws(160.0), CFG)
    assert not small["capped"].any()
    assert big["capped"].dtype == bool
