"""ConnectedSolutions revenue per battery block.

Kept in physical units as well as dollars: eligible grid-program kW per
block (average kW performed across events, after the overlap with the
site's own peak days), so the report can reprice it.
"""

import numpy as np


def grid_revenue(site: dict, peak_kw, blocks, cfg: dict) -> dict:
    """Eligible kW and dollars per block per year, one value per draw.

    The kW counted per block is the lesser of the block's power and the
    program's export cap (1.5 times the site's peak, shared over its
    blocks), then scaled by the performance and overlap factors.
    """
    cs = cfg["connected_solutions"]
    peak_kw = np.asarray(peak_kw, dtype=float)
    if site["utility"] not in cs["eligible_utilities"]["value"]:
        return {"grid_kw": np.zeros(peak_kw.shape), "grid_usd": np.zeros(peak_kw.shape)}
    cap = cs["export_cap_share_of_site_peak"]["value"] * peak_kw / blocks
    counted = np.minimum(cfg["battery"]["block"]["power_kw"], cap)
    kw = (
        counted
        * cs["performance_factor"]["value"]
        * (1 - cs["overlap_factor"]["value"])
    )
    rate = cs["daily_dispatch_usd_per_kw_season"]["value"]
    return {"grid_kw": kw, "grid_usd": kw * rate}
