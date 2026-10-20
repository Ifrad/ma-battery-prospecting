from prospect.priors import config
from prospect.validate import run

CFG = config.load()


def metrics(model, size, n=100):
    return {
        "model": {"n": n, "spearman": 0.5, "mdape": model},
        "size": {"n": n, "spearman": 0.4, "mdape": size},
    }


def results(hit=0.79, worcester_firm=0.0):
    pilot = {
        "all": metrics(0.7, 0.8),
        "warehouse": metrics(0.6, 0.9),
        "manufacturing": metrics(0.8, 0.7),
        "hospital": metrics(0.1, 0.9, n=13),
    }
    site = {"p_top15": 0.6}
    return {
        "energy": {"pilot": pilot, "statewide": {"all": metrics(0.7, 0.8, n=8000)}},
        "calibration": {"all": {"hit": hit}},
        "stability": {
            "metro_south": [site] * 3,
            "worcester": [{"p_top15": worcester_firm}] * 3,
        },
        "stress": {
            "regions": {
                "metro_south": {"top15_kept": 14},
                "worcester": {"top15_kept": 8},
            }
        },
    }


def test_wins_split_segments_and_skip_small_ones():
    better, not_better = run.wins(results()["energy"]["pilot"])
    assert better == ["warehouse"] and not_better == ["manufacturing"]


def test_summary_follows_the_numbers():
    text = "\n".join(run.summary(results(), CFG))
    assert "calibrated overall" in text
    assert "Worcester's ranking is a tier" in text
    assert "Metro South's ranking is a tier" not in text
    off = "\n".join(run.summary(results(hit=0.6, worcester_firm=0.9), CFG))
    assert "not calibrated" in off and "is a tier" not in off
