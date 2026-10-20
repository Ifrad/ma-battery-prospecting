"""ConnectedSolutions revenue per battery block.

Kept in physical units as well as dollars: eligible grid-program kW per
block (average kW performed across events, after the overlap with the
site's own peak days), so the report can reprice it.
"""

import numpy as np


def event_ratios(site: dict, cfg: dict) -> dict:
    """Median event-window load over annual peak for the site's type: the
    summer weekday 3 to 8 p.m. mean, and the all-year weekday 3 to 8 p.m.
    peak. Types with no open profile take the pooled medians."""
    sim = cfg["simulation"]
    t = sim["types"].get(site.get("profile"))
    e = (t or sim["pooled"])["event_window"]
    return {k: e[k]["median"] for k in ("mean_over_peak", "peak_over_peak")}


def grid_revenue(site: dict, peak_kw, blocks, cfg: dict, g3_weight=0.0) -> dict:
    """Eligible kW and dollars per block per year, one value per draw.

    Without export (the default), the kW counted per block is the lesser of
    the block's average event output (power times the performance factor)
    and the building's mean event-window load per block. With export, it is
    the block's power capped at 1.5 times the site peak, where a G-3 site's
    peak is its 3 to 8 p.m. peak, times the performance factor. Both are
    then reduced by the overlap factor.
    """
    cs = cfg["connected_solutions"]
    peak_kw = np.asarray(peak_kw, dtype=float)
    if site["utility"] not in cs["eligible_utilities"]["value"]:
        return {"grid_kw": np.zeros(peak_kw.shape), "grid_usd": np.zeros(peak_kw.shape)}
    power = cfg["battery"]["block"]["power_kw"]
    perf = cs["performance_factor"]["value"]
    ratio = event_ratios(site, cfg)
    if cs["site_exports"]["value"]:
        is_g3 = np.asarray(g3_weight) > 0.5
        ref = peak_kw * np.where(is_g3, ratio["peak_over_peak"], 1.0)
        cap = cs["export_cap_share_of_site_peak"]["value"] * ref / blocks
        counted = np.minimum(power, cap) * perf
    else:
        load = ratio["mean_over_peak"] * peak_kw / blocks
        counted = np.minimum(power * perf, load)
    kw = counted * (1 - cs["overlap_factor"]["value"])
    rate = cs["daily_dispatch_usd_per_kw_season"]["value"]
    return {"grid_kw": kw, "grid_usd": kw * rate}
