import pytest

from prospect.priors import config
from prospect.validate import stress

CFG = config.load()


def test_scaled_cuts_every_share_cell_and_leaves_cfg_alone():
    out = stress.scaled(CFG, 0.5)
    base = CFG["simulation"]["pooled"]["bins"]["under_200"]["all_hours"]["median"]
    cut = out["simulation"]["pooled"]["bins"]["under_200"]["all_hours"]["median"]
    assert cut == pytest.approx(base * 0.5)
    office = out["simulation"]["types"]["SmallOffice"]["bins"]["under_200"]
    assert office["peak_window"]["p90"] == pytest.approx(
        CFG["simulation"]["types"]["SmallOffice"]["bins"]["under_200"]["peak_window"][
            "p90"
        ]
        * 0.5
    )
    assert (
        CFG["simulation"]["pooled"]["bins"]["under_200"]["all_hours"]["median"] == base
    )


def site(i, value, no_profile=False):
    return {
        "site_id": f"s{i}",
        "value_p50": value,
        "blocks": 1.0,
        "total_p50": value,
        "no_profile": no_profile,
    }


def test_compare_counts_kept_sites_and_drops():
    base = {
        r: [site(i, 100 - i, no_profile=i < 2) for i in range(60)]
        for r in stress.REGIONS
    }
    moved = [site(i, 100 - i) for i in range(2, 60)] + [site(0, 1), site(1, 0)]
    stressed = {r: moved for r in stress.REGIONS}
    out = stress.compare(base, stressed)["worcester"]
    assert out["top15_kept"] == 13 and out["top50_kept"] == 48
    assert out["dropped_from_top15"] == ["s0", "s1"]
    assert out["no_profile_in_top15"] == (2, 0)
