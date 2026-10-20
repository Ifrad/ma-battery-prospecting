"""Which inputs drive a site's value per block, by rank correlation across
its draws. Inputs fixed for every draw (rates, performance and overlap
factors, the realization factor) cannot show here; see the one-at-a-time
sensitivity instead.
"""

import numpy as np

INPUTS = ("annual_kwh", "load_factor", "peak_kw", "blocks", "reduction_share")


def ranks(x: np.ndarray) -> np.ndarray:
    """Ranks starting at 0, with ties sharing their average rank."""
    _, inverse, counts = np.unique(x, return_inverse=True, return_counts=True)
    ends = np.cumsum(counts)
    return ((ends - counts + ends - 1) / 2)[inverse]


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    if np.ptp(a) == 0 or np.ptp(b) == 0:
        return 0.0
    return float(np.corrcoef(ranks(a), ranks(b))[0, 1])


def top_drivers(x: dict, k: int = 3) -> list[tuple[str, float]]:
    """The k inputs most rank-correlated with value per block, signed."""
    rho = {name: spearman(x[name], x["value_per_block"]) for name in INPUTS}
    ranked = sorted(rho.items(), key=lambda kv: -abs(kv[1]))
    return [(name, round(r, 2)) for name, r in ranked[:k] if r != 0]
