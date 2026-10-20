import pytest

from prospect.model import cost
from prospect.priors import config

CFG = config.load()


def test_crf_matches_the_annuity_formula():
    assert cost.crf(0.08, 10) == pytest.approx(0.149029, rel=1e-5)


def test_break_even_is_higher_for_higher_value_and_zero_for_no_value():
    low, high = cost.break_even(20_000, CFG, False), cost.break_even(40_000, CFG, False)
    assert 0 < low < high
    assert cost.break_even(0, CFG, False) == 0
    assert cost.break_even(3_000, CFG, False) == 0  # below O&M


def test_break_even_round_trips_through_annual_cost():
    be = cost.break_even(30_000, CFG, itc=True)
    assert cost.annual_cost(be, CFG, itc=True) == pytest.approx(30_000)


def test_itc_raises_break_even_only_under_one_megawatt():
    base = cost.break_even(30_000, CFG, itc=False)
    assert cost.break_even(30_000, CFG, itc=True, blocks=3) == pytest.approx(base / 0.7)
    assert cost.break_even(30_000, CFG, itc=True, blocks=4) == pytest.approx(base)
