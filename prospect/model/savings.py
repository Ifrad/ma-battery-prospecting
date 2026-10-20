"""Battery blocks per site and demand savings per block.

Demand savings are kept in physical units as well as dollars: kW-months of
billed peak reduction under each schedule, per block per year, so the report
can reprice them when rates change.
"""

import numpy as np

from prospect.model.draws import from_spread, rng

NGRID = "National Grid (Massachusetts Electric)"
EVERSOURCE = "Eversource Energy (NSTAR Electric)"


def blocks(peak_kw: np.ndarray, cfg: dict) -> np.ndarray:
    """Whole battery blocks per draw: one per peak_kw_per_block, at least one."""
    rule = cfg["model"]["blocks"]
    n = np.maximum(1, np.floor(peak_kw / rule["peak_kw_per_block"]))
    if rule["max_blocks"] is not None:
        n = np.minimum(n, rule["max_blocks"])
    return n


def bin_label(peak_kw: np.ndarray, cfg: dict) -> np.ndarray:
    """Size bin of each draw's peak per block, from config/simulation.yaml."""
    labels = np.empty(peak_kw.shape, dtype=object)
    for label, (lo, hi) in cfg["simulation"]["bins_kw"].items():
        upper = np.inf if hi is None else hi
        labels[(peak_kw >= lo) & (peak_kw < upper)] = label
    return labels


def reduction_share(site: dict, peak_per_block: np.ndarray, case: str, cfg: dict):
    """Monthly peak reduction share per draw, before the realization factor.

    case is all_hours (G-2) or peak_window (G-3). The share comes from the
    site's simulated type in the size bin of its peak per block.
    """
    sim = cfg["simulation"]
    g = rng(site["site_id"], 3)
    if site["profile"] == "no open profile":
        env = sim["no_open_profile"][case]
        return g.uniform(env["low"], env["high"], peak_per_block.shape)
    if site["profile"] == "placeholder mix":
        cells = sim["pooled"]["bins"]
    else:
        cells = sim["types"][site["profile"]]["bins"]
    z = g.standard_normal(peak_per_block.shape)
    labels = bin_label(peak_per_block, cfg)
    share = np.zeros(peak_per_block.shape)
    for label in np.unique(labels):
        mask = labels == label
        share[mask] = from_spread(cells[label][case], z[mask])
    return np.clip(share, 0.0, 1.0)


def schedule_rates(utility: str, cfg: dict) -> dict:
    """Demand charge per kW-month by schedule name for a utility."""
    schedules = cfg["rates"]["utilities"][utility]["schedules"]
    return {s["name"]: s["demand_charge_per_kw_month"] for s in schedules}


def schedule_weights(site: dict, kwh_month, peak_kw, cfg: dict):
    """(G-2 weight, G-3 weight) per draw; G-1 draws get neither."""
    if site["utility"] == EVERSOURCE:
        g1_max = next(
            s["eligibility"]["max_kw"]
            for s in cfg["rates"]["utilities"][EVERSOURCE]["schedules"]
            if s["name"] == "G-1"
        )
        return (peak_kw > g1_max).astype(float), np.zeros_like(peak_kw)
    band = cfg["model"]["rate_band_kw"]
    g1_max = next(
        s["eligibility"]["max_kwh_per_month"]
        for s in cfg["rates"]["utilities"][NGRID]["schedules"]
        if s["name"] == "G-1"
    )
    demand = kwh_month > g1_max
    w3 = np.clip(
        (peak_kw - band["g2_below"]) / (band["g3_above"] - band["g2_below"]), 0, 1
    )
    return demand * (1 - w3), demand * w3


def demand_savings(site: dict, d: dict, cfg: dict) -> dict:
    """Blocks, kW-months per block under G-2 and G-3, and dollars per block."""
    n = blocks(d["peak_kw"], cfg)
    per_block = d["peak_kw"] / n
    real = cfg["profiles"]["realization_factor"]["value"]
    w2, w3 = schedule_weights(site, d["annual_kwh"] / 12, d["peak_kw"], cfg)
    share_g2 = reduction_share(site, per_block, "all_hours", cfg)
    share_g3 = reduction_share(site, per_block, "peak_window", cfg)
    # The simulated share comes from buildings whose reduction never exceeds
    # the block's power, so the kW cut is capped at it here too.
    power = cfg["battery"]["block"]["power_kw"]
    kwm_g2 = 12 * w2 * np.minimum(share_g2 * per_block, power) * real
    kwm_g3 = 12 * w3 * np.minimum(share_g3 * per_block, power) * real
    rates = schedule_rates(site["utility"], cfg)
    usd = kwm_g2 * rates["G-2"] + kwm_g3 * rates.get("G-3", 0.0)
    return {
        "blocks": n,
        "reduction_share": w2 * share_g2 + w3 * share_g3,
        "kwm_g2": kwm_g2,
        "kwm_g3": kwm_g3,
        "demand_usd": usd,
    }
