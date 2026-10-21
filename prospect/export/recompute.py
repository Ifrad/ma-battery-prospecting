"""Recompute value per block, expected blocks and the stream split from the
export alone, as the report does in the browser. This is the reference the
report's JavaScript mirrors line for line; tests check both against the
Python model (prospect/model/).
"""

import numpy as np


def defaults(manifest: dict) -> dict:
    """The settings the report starts from: the model's own inputs."""
    cs = manifest["connected_solutions"]
    return {
        "connected_solutions": True,
        "realization_factor": manifest["realization_factor"]["value"],
        "performance_factor": cs["performance_factor"]["value"],
        "overlap_factor": cs["overlap_factor"]["value"],
        "site_exports": cs["site_exports"],
        "rates": manifest["demand_rates_usd_per_kw_month"],
    }


def value_draws(site: dict, manifest: dict, settings: dict) -> dict:
    """Per draw: demand savings, ConnectedSolutions revenue, value per block
    and total, in dollars per year."""
    d = site["draws"]
    kwm_g2, kwm_g3 = np.asarray(d["kwm_g2"], float), np.asarray(d["kwm_g3"], float)
    blocks, peak = np.asarray(d["blocks"], float), np.asarray(d["peak_kw"], float)
    g3 = np.asarray(d["g3"], bool)
    rates = settings["rates"][site["utility"]]
    base_real = manifest["realization_factor"]["value"]
    demand = (kwm_g2 * rates["G-2"] + kwm_g3 * rates.get("G-3", 0.0)) * (
        settings["realization_factor"] / base_real
    )
    cs = manifest["connected_solutions"]
    grid = np.zeros_like(demand)
    if settings["connected_solutions"] and site["utility"] in cs["eligible_utilities"]:
        power = manifest["battery_block"]["power_kw"]
        perf = settings["performance_factor"]
        ratio = site["event_window"]
        if settings["site_exports"]:
            ref = peak * np.where(g3, ratio["peak_over_peak"], 1.0)
            cap = cs["export_cap_share_of_site_peak"] * ref / blocks
            counted = np.minimum(power, cap) * perf
        else:
            counted = np.minimum(power * perf, ratio["mean_over_peak"] * peak / blocks)
        grid = counted * (1 - settings["overlap_factor"]) * cs["usd_per_kw_season"]
    value = demand + grid
    return {"demand": demand, "grid": grid, "value": value, "total": value * blocks}


def percentiles(x: np.ndarray) -> dict:
    p10, p50, p90 = np.percentile(x, [10, 50, 90])
    return {"p10": float(p10), "p50": float(p50), "p90": float(p90)}


def site_summary(site: dict, manifest: dict, settings: dict) -> dict:
    """What the report shows for one site under the given settings."""
    x = value_draws(site, manifest, settings)
    demand, grid = float(np.median(x["demand"])), float(np.median(x["grid"]))
    total = demand + grid
    return {
        "value_per_block": percentiles(x["value"]),
        "total": percentiles(x["total"]),
        "blocks": float(np.mean(site["draws"]["blocks"])),
        "streams": {
            "demand_savings": {
                "p50": demand,
                "share": demand / total if total > 0 else 0.0,
            },
            "connected_solutions": {
                "p50": grid,
                "share": grid / total if total > 0 else 0.0,
            },
        },
        "values": x["value"],
    }
