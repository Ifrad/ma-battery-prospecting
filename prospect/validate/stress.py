"""Peak shape stress test: rescore with the simulated peak reduction share
cut, since peak shape is unvalidated (config/validate.yaml).

Every site's share is multiplied by the all_sites factor, and sites with no
open profile by their own factor instead. Only demand savings change;
ConnectedSolutions does not depend on the share. Simulated values.
"""

import copy

import numpy as np

from prospect.model import score
from prospect.model.report import rank_key
from prospect.model.run import load_scope
from prospect.sites.match_rates import table

REGIONS = {"metro_south": "Metro South", "worcester": "Worcester"}
TOPS = (15, 50)
SCENARIO = "with_connected_solutions"


def scaled(cfg: dict, factor: float) -> dict:
    """A copy of cfg with every simulated peak reduction share times factor."""
    out = copy.deepcopy(cfg)
    sim = out["simulation"]
    cells = [c for t in sim["types"].values() for c in t["bins"].values()]
    cells += list(sim["pooled"]["bins"].values())
    for c in cells:
        for case in ("all_hours", "peak_window"):
            for q in ("p10", "median", "p90"):
                if c[case][q] is not None:
                    c[case][q] *= factor
    return out


def scored(scope: list, cfg: dict, stress: dict | None) -> dict:
    """P50 value per block and the ranking fields per site, by region."""
    cfgs = {}
    if stress:
        cfgs = {
            "typed": scaled(cfg, stress["all_sites"]),
            "no_profile": scaled(cfg, stress["no_open_profile"]),
        }
    out = {r: [] for r in REGIONS}
    for site, buildings in scope:
        c = cfg
        if stress:
            c = cfgs["no_profile" if site["profile"] == "no open profile" else "typed"]
        r = next(
            x for x in score.score_site(site, buildings, c) if x["scenario"] == SCENARIO
        )
        out[site["region"]].append(
            {
                "site_id": site["site_id"],
                "value_p50": r["value_per_block"]["p50"],
                "blocks": r["blocks"],
                "total_p50": r["total"]["p50"],
                "no_profile": site["profile"] == "no open profile",
            }
        )
    return {k: sorted(v, key=rank_key) for k, v in out.items()}


def compare(base: dict, stressed: dict) -> dict:
    out = {}
    for region in REGIONS:
        b, s = base[region], stressed[region]
        sv = {x["site_id"]: x["value_p50"] for x in s}
        change = [
            sv[x["site_id"]] / x["value_p50"] - 1 for x in b if x["value_p50"] > 0
        ]
        out[region] = {
            "sites": len(b),
            "median_change": float(np.median(change)),
            **{
                f"top{k}_kept": len(
                    {x["site_id"] for x in b[:k]} & {x["site_id"] for x in s[:k]}
                )
                for k in TOPS
            },
            "dropped_from_top15": [
                x["site_id"]
                for x in b[:15]
                if x["site_id"] not in {y["site_id"] for y in s[:15]}
            ],
            "no_profile_in_top15": (
                sum(x["no_profile"] for x in b[:15]),
                sum(x["no_profile"] for x in s[:15]),
            ),
        }
    return out


def results(conn, cfg: dict) -> dict:
    scope = load_scope(conn, cfg)
    stress = cfg["validate"]["peak_shape_stress"]
    r = compare(scored(scope, cfg, None), scored(scope, cfg, stress))
    owners = dict(
        conn.execute(
            "SELECT site_id, owner FROM sites WHERE site_id = ANY(%s)",
            ([s for v in r.values() for s in v["dropped_from_top15"]],),
        ).fetchall()
    )
    for v in r.values():
        v["dropped_owners"] = [owners[s] for s in v["dropped_from_top15"]]
    return {"stress": stress, "regions": r}


def section(r: dict) -> list[str]:
    st = r["stress"]
    rows = []
    for k, label in REGIONS.items():
        v = r["regions"][k]
        rows.append(
            [
                label,
                v["sites"],
                f"{v['median_change']:+.0%}",
                f"{v['top15_kept']} of 15",
                f"{v['top50_kept']} of 50",
                f"{v['no_profile_in_top15'][0]} to {v['no_profile_in_top15'][1]}",
            ]
        )
    out = [
        "## Peak shape stress test",
        "",
        "Peak shape is unvalidated: it was only stress-tested. Every site is"
        " rescored with the simulated monthly peak reduction share cut by"
        f" {1 - st['all_sites']:.0%}, and sites with no open profile by"
        f" {1 - st['no_open_profile']:.0%} instead (owner's stress values,"
        " config/validate.yaml). Only demand savings change. Value per block"
        " with ConnectedSolutions, simulated.",
        "",
        table(
            [
                "Region",
                "Scored sites",
                "Median change in P50 value per block",
                "Top 15 kept",
                "Top 50 kept",
                "No-profile sites in top 15, before to after",
            ],
            rows,
        ),
    ]
    for k, label in REGIONS.items():
        names = r["regions"][k]["dropped_owners"]
        out += [
            "",
            f"{label}, dropped out of the top 15: "
            + ("; ".join(names) or "none")
            + ".",
        ]
    return out
