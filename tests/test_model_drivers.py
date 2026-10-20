import numpy as np
import pytest

from prospect.model import drivers


def test_ranks_average_ties():
    assert list(drivers.ranks(np.array([3.0, 1.0, 3.0, 2.0]))) == [2.5, 0, 2.5, 1]


def test_spearman_is_one_for_any_increasing_link_and_zero_for_a_constant():
    a = np.linspace(1, 10, 50)
    assert drivers.spearman(a, a**3) == pytest.approx(1.0)
    assert drivers.spearman(a, -np.exp(a)) == pytest.approx(-1.0)
    assert drivers.spearman(np.ones(50), a) == 0.0


def test_top_drivers_rank_by_strength_and_skip_constant_inputs():
    g = np.random.default_rng(0)
    kwh = g.uniform(1, 2, 500)
    lf = g.uniform(0.3, 0.6, 500)
    x = {
        "annual_kwh": kwh,
        "load_factor": lf,
        "peak_kw": kwh / lf,
        "blocks": np.ones(500),
        "reduction_share": g.uniform(0, 1, 500),
        "value_per_block": 10 * kwh - lf,
    }
    top = drivers.top_drivers(x)
    assert top[0][0] == "annual_kwh" and top[0][1] > 0.9
    assert "blocks" not in [name for name, _ in top]
