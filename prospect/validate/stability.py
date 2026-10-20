"""Rank stability from the stored draws of the latest score run.

Draw i of every site in a region is taken as one joint outcome (each site's
draws are seeded on their own, so sites vary independently). In each outcome
the region's sites are ranked by value per block with ConnectedSolutions;
a site's probability of being in the top k is the share of outcomes where it
is. No new draws are made.
"""

import numpy as np

from prospect.model.report import rank_key
from prospect.model.run import value_draws
from prospect.sites.match_rates import table

REGIONS = {"metro_south": "Metro South", "worcester": "Worcester"}
TOPS = (15, 50)

LATEST = """
    SELECT s.site_id, s.region, s.utility, s.scenario, s.value_p50, s.blocks,
           s.total_p50, s.kwm_g2, s.kwm_g3, s.grid_kw, st.owner
    FROM site_scores s JOIN sites st USING (site_id)
    WHERE s.run_id = (SELECT max(run_id) FROM score_runs)
        AND s.scenario = 'with_connected_solutions' AND s.region = %s
"""


def ranks(values: np.ndarray) -> np.ndarray:
    """Rank of each site (1 is highest) in each draw: sites x draws."""
    order = np.argsort(-values, axis=0, kind="stable")
    out = np.empty_like(order)
    rows = np.arange(values.shape[0])[:, None]
    out[order, np.arange(values.shape[1])] = rows + 1
    return out


def region_stability(sites: list[dict], cfg: dict) -> list[dict]:
    """Per site: P(top 15), P(top 50) and the P10 to P90 range of its rank."""
    values = np.array([value_draws(s, cfg) for s in sites])
    r = ranks(values)
    out = []
    for s, rk in zip(sites, r, strict=True):
        lo, hi = np.percentile(rk, [10, 90])
        out.append(
            {
                **{
                    k: s[k]
                    for k in ("site_id", "owner", "value_p50", "blocks", "total_p50")
                },
                **{f"p_top{k}": float(np.mean(rk <= k)) for k in TOPS},
                "rank_p10": int(lo),
                "rank_p90": int(hi),
            }
        )
    return sorted(out, key=rank_key)


def results(conn, cfg: dict) -> dict:
    out = {}
    for region in REGIONS:
        cur = conn.execute(LATEST, (region,))
        names = [d.name for d in cur.description]
        sites = [dict(zip(names, r, strict=True)) for r in cur.fetchall()]
        out[region] = region_stability(sites, cfg)
    return out


def tier_statement(label: str, rs: list[dict]) -> str:
    """Plain words on whether the region's ranking is an order or a tier."""
    firm = sum(x["p_top15"] > 0.9 for x in rs)
    likely15 = sum(x["p_top15"] > 0.5 for x in rs)
    likely50 = sum(x["p_top50"] > 0.5 for x in rs)
    if firm:
        head = (
            f"{label}: {firm} sites are in the top 15 in more than 90 percent of"
            f" draws and {likely15} in more than half, so the head of the list is"
            " an order; below it the ranking is a tier"
        )
    else:
        head = (
            f"{label}: no site is in the top 15 in more than 90 percent of draws"
            f" ({likely15} in more than half), so the ranking is a tier, not an"
            " order"
        )
    return (
        f"- {head}: {likely50} sites are more likely than not in the top 50, and"
        " their order inside that group is not meaningful."
    )


def section(r: dict) -> list[str]:
    summary = []
    for k, label in REGIONS.items():
        rs = r[k]
        summary.append(
            [
                label,
                len(rs),
                *(sum(x[f"p_top{t}"] > 0.5 for x in rs) for t in TOPS),
                *(sum(x[f"p_top{t}"] > 0.9 for x in rs) for t in TOPS),
            ]
        )
    out = [
        "## Rank stability",
        "",
        "From the stored draws of the latest score run, with ConnectedSolutions:"
        " draw i of every site in a region is one joint outcome, sites ranked"
        " by value per block in each. Simulated values, so this is stability"
        " under the model's own uncertainty, not accuracy.",
        "",
        table(
            [
                "Region",
                "Scored sites",
                "P(top 15) over 50%",
                "P(top 50) over 50%",
                "P(top 15) over 90%",
                "P(top 50) over 90%",
            ],
            summary,
        ),
    ]
    out += ["", *(tier_statement(label, r[k]) for k, label in REGIONS.items())]
    for k, label in REGIONS.items():
        out += [
            "",
            f"{label}, the 15 sites with the highest P50, with the 80 percent"
            " range of their rank across draws:",
            "",
            table(
                ["Rank by P50", "Owner", "P(top 15)", "P(top 50)", "Rank P10 to P90"],
                [
                    [
                        i + 1,
                        x["owner"],
                        f"{x['p_top15']:.0%}",
                        f"{x['p_top50']:.0%}",
                        f"{x['rank_p10']} to {x['rank_p90']}",
                    ]
                    for i, x in enumerate(r[k][:15])
                ],
            ),
        ]
    return out
