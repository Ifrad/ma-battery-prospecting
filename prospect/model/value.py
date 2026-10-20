"""Value per battery block: yearly demand savings plus grid program revenue,
gross, before any host share. Simulated and unvalidated; not profit.
"""

import numpy as np

from prospect.model import draws, grid, savings


def pct(x: np.ndarray) -> dict:
    p10, p50, p90 = np.percentile(x, [10, 50, 90])
    return {"p10": float(p10), "p50": float(p50), "p90": float(p90)}


def site_draws(site: dict, buildings: list[dict], cfg: dict, streams: tuple) -> dict:
    """Per draw: energy, peak, blocks, each stream and value per block."""
    d = draws.site_draws(site, buildings, cfg)
    s = savings.demand_savings(site, d, cfg)
    n = len(d["peak_kw"])
    g = (
        grid.grid_revenue(site, n, cfg)
        if "connected_solutions" in streams
        else {"grid_kw": np.zeros(n), "grid_usd": np.zeros(n)}
    )
    value = s["demand_usd"] + g["grid_usd"]
    return {**d, **s, **g, "value_per_block": value, "total": value * s["blocks"]}


def summary(x: dict) -> dict:
    """P10, P50 and P90 of value per block and total, and mean blocks."""
    return {
        "value_per_block": pct(x["value_per_block"]),
        "total": pct(x["total"]),
        "blocks": float(np.mean(x["blocks"])),
    }


STREAMS = {"demand": "demand_usd", "connected_solutions": "grid_usd"}


def by_stream(x: dict) -> dict:
    """P50 per block of each stream and its share of their sum."""
    p50 = {k: float(np.median(x[col])) for k, col in STREAMS.items()}
    total = sum(p50.values())
    return {
        k: {"p50": v, "share": v / total if total > 0 else 0.0} for k, v in p50.items()
    }
