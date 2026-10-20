import numpy as np

from prospect.validate import stability


def test_ranks_per_draw_with_one_as_highest():
    values = np.array([[3.0, 1.0], [2.0, 3.0], [1.0, 2.0]])  # 3 sites, 2 draws
    assert stability.ranks(values).tolist() == [[1, 3], [2, 1], [3, 2]]


def test_tier_statement_says_order_or_tier():
    firm = [{"p_top15": 0.95, "p_top50": 1.0}] * 3
    loose = [{"p_top15": 0.3, "p_top50": 0.6}] * 20
    assert "an order" in stability.tier_statement("A", firm)
    assert "a tier, not an order" in stability.tier_statement("B", loose)
    assert "20 sites are more likely than not" in stability.tier_statement("B", loose)
