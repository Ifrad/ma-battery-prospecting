"""Score one site under each scenario: value per block, blocks, total and
break-even installed cost. Reads nothing from the database; see
prospect/model/run.py for that.
"""

import numpy as np

from prospect.model import cost, drivers, value

EVERSOURCE = "Eversource Energy (NSTAR Electric)"


def flags(site: dict, x: dict) -> list[str]:
    """The site's funnel flags plus the scoring flags.

    capped: in most draws one block's cut reaches its power limit, so value
    per block is at the one-block ceiling. rate_area_unconfirmed: Eversource
    sites (Canton and Sharon), whose rate area is a placeholder.
    """
    out = list(site.get("flags") or [])
    if np.mean(x["capped"]) > 0.5:
        out.append("capped")
    if site["utility"] == EVERSOURCE:
        out.append("rate_area_unconfirmed")
    return out


def score_site(site: dict, buildings: list[dict], cfg: dict) -> list[dict]:
    """One result per scenario, each keeping its draws."""
    out = []
    for name, streams in cfg["model"]["scenarios"].items():
        x = value.site_draws(site, buildings, cfg, tuple(streams))
        s = value.summary(x)
        out.append(
            {
                "scenario": name,
                **s,
                "break_even": cost.break_even_summary(
                    x["value_per_block"], s["blocks"], cfg
                ),
                "streams": value.by_stream(x),
                "drivers": drivers.top_drivers(x),
                "flags": flags(site, x),
                "draws": x,
            }
        )
    return out
