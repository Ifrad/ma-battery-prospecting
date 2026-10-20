"""Score one site under each scenario: value per block, blocks, total and
break-even installed cost. Reads nothing from the database; see
prospect/model/run.py for that.
"""

from prospect.model import cost, drivers, value


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
                "draws": x,
            }
        )
    return out
