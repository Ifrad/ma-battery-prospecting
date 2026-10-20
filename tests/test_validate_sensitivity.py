from prospect.validate import sensitivity


def test_compare_counts_kept_left_joined_and_rank_moves():
    base = {r: [f"s{i}" for i in range(60)] for r in sensitivity.REGIONS}
    # s0 and s1 regroup into a new site id; everything else shifts up by two.
    case = {r: [f"s{i}" for i in range(2, 60)] + ["new"] for r in sensitivity.REGIONS}
    out = sensitivity.compare(base, case)["metro_south"]
    assert out["left"] == 2 and out["joined"] == 1
    assert out["top50_overlap"] == 48
    assert out["median_rank_move_in_top50"] == 2


def test_the_two_cases_change_only_their_assumption():
    sites = {"touch_tolerance_m": {"value": 1.0}}
    codes = {"classes": {"mixed_commercial_industrial": {}, "hospital": {}}}
    sensitivity.touch_5m(sites, codes)
    assert sites["touch_tolerance_m"]["value"] == 5.0 and len(codes["classes"]) == 2
    sensitivity.no_03x_04x(sites, codes)
    assert list(codes["classes"]) == ["hospital"]
