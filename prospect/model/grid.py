"""ConnectedSolutions revenue per battery block.

Kept in physical units as well as dollars: eligible grid-program kW per
block (average kW performed across events, after the overlap with the
site's own peak days), so the report can reprice it.
"""

import numpy as np


def grid_revenue(site: dict, n: int, cfg: dict) -> dict:
    """Eligible kW and dollars per block per year, for n draws."""
    cs = cfg["connected_solutions"]
    if site["utility"] not in cs["eligible_utilities"]["value"]:
        return {"grid_kw": np.zeros(n), "grid_usd": np.zeros(n)}
    kw = (
        cfg["battery"]["block"]["power_kw"]
        * cs["performance_factor"]["value"]
        * (1 - cs["overlap_factor"]["value"])
    )
    rate = cs["daily_dispatch_usd_per_kw_season"]["value"]
    return {"grid_kw": np.full(n, kw), "grid_usd": np.full(n, kw * rate)}
