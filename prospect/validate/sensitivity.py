"""Data assumption sensitivity, run in throwaway databases.

Usage: python -m prospect.validate.sensitivity (make sensitivity)

For each case, copies the real database to a throwaway one (CREATE DATABASE
... TEMPLATE), rebuilds sites there with one assumption changed in memory,
recomputes the intensity priors and the funnel in memory, scores, and drops
the copy. The real tables and the files in config/ and docs/ are never
changed. Results go to data/validate/sensitivity.json for make validate.
"""

import copy
import json
import os
import sys
from pathlib import Path

from prospect import use_codes
from prospect.db import connect
from prospect.model import score
from prospect.model.report import rank_key
from prospect.model.run import load_scope
from prospect.priors import config, funnel, intensity
from prospect.sites import build, group
from prospect.sites.match_rates import table

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "validate" / "sensitivity.json"
REGIONS = {"metro_south": "Metro South", "worcester": "Worcester"}
TOP = 50
SCRATCH = "prospect_sensitivity"


def touch_5m(sites_cfg: dict, codes_cfg: dict) -> None:
    sites_cfg["touch_tolerance_m"]["value"] = 5.0


def no_03x_04x(sites_cfg: dict, codes_cfg: dict) -> None:
    del codes_cfg["classes"]["mixed_commercial_industrial"]


CASES = {
    "touch tolerance 5 m instead of 1 m": touch_5m,
    "03x and 04x classes removed": no_03x_04x,
}


def ranking(conn, cfg: dict) -> dict:
    """Scored sites by region, ranked by value per block with ConnectedSolutions."""
    out = {r: [] for r in REGIONS}
    for site, buildings in load_scope(conn, cfg):
        r = next(
            x
            for x in score.score_site(site, buildings, cfg)
            if x["scenario"] == "with_connected_solutions"
        )
        out[site["region"]].append(
            {
                "site_id": site["site_id"],
                "value_p50": r["value_per_block"]["p50"],
                "blocks": r["blocks"],
                "total_p50": r["total"]["p50"],
            }
        )
    return {k: [x["site_id"] for x in sorted(v, key=rank_key)] for k, v in out.items()}


def rebuild(conn, change) -> dict:
    """Rebuild sites, priors and funnel in the throwaway database; return cfg."""
    sites_cfg = group.load_config()
    codes_cfg = use_codes.load()
    change(sites_cfg, codes_cfg)
    real = (group.load_config, use_codes.load)
    group.load_config = lambda path=None: copy.deepcopy(sites_cfg)
    use_codes.load = lambda path=None: copy.deepcopy(codes_cfg)
    try:
        build.build(conn)
    finally:
        group.load_config, use_codes.load = real
    cfg = config.load()
    cfg["intensity"]["segments"] = intensity.summarize(
        intensity.pilot_rows(conn), intensity.healthcare_rows(conn)
    )
    rows = [funnel.evaluate(s, b, cfg) for s, b in funnel.load_inputs(conn)]
    funnel.store(conn, rows)
    conn.commit()
    return cfg


def scratch(sql: str) -> None:
    with connect(autocommit=True, dbname="postgres") as admin:
        admin.execute(sql)


def run_case(name: str, change) -> dict:
    real_db = os.environ.get("POSTGRES_DB", "prospect")
    scratch(f"DROP DATABASE IF EXISTS {SCRATCH}")
    scratch(f"CREATE DATABASE {SCRATCH} TEMPLATE {real_db}")
    try:
        with connect(dbname=SCRATCH) as conn:
            cfg = rebuild(conn, change)
            return ranking(conn, cfg)
    finally:
        scratch(f"DROP DATABASE IF EXISTS {SCRATCH}")


def compare(base: dict, case: dict) -> dict:
    out = {}
    for region in REGIONS:
        b, c = base[region], case[region]
        rank_b = {s: i for i, s in enumerate(b)}
        rank_c = {s: i for i, s in enumerate(c)}
        both = set(b[:TOP]) & set(c[:TOP])
        moves = sorted(abs(rank_b[s] - rank_c[s]) for s in both)
        out[region] = {
            "scored_before": len(b),
            "scored_after": len(c),
            "left": len(set(b) - set(c)),
            "joined": len(set(c) - set(b)),
            "top50_overlap": len(both),
            "median_rank_move_in_top50": moves[len(moves) // 2] if moves else 0,
        }
    return out


def main() -> int:
    with connect() as conn:
        base = ranking(conn, config.load())
    results = {}
    for name, change in CASES.items():
        print(f"running: {name}", flush=True)
        results[name] = compare(base, run_case(name, change))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2))
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


def section() -> list[str]:
    head = [
        "## Data assumption sensitivity",
        "",
        "Each case rebuilds sites, priors, the funnel and the scores in a"
        " throwaway copy of the database with one assumption changed, and"
        f" compares the top {TOP} per region by value per block with the"
        " current ranking. Sites are matched by site id, so a site whose"
        " parcels regroup counts as leaving and joining. Run `make"
        " sensitivity` to refresh it.",
    ]
    if not OUT.exists():
        return [*head, "", "Not run yet on this machine."]
    r = json.loads(OUT.read_text())
    rows = [
        [
            name,
            label,
            f"{v['scored_before']} to {v['scored_after']}",
            v["left"],
            v["joined"],
            f"{v['top50_overlap']} of {TOP}",
            v["median_rank_move_in_top50"],
        ]
        for name, regions in r.items()
        for k, label in REGIONS.items()
        for v in [regions[k]]
    ]
    return [
        *head,
        "",
        table(
            [
                "Case",
                "Region",
                "Scored sites",
                "Left",
                "Joined",
                f"Top {TOP} kept",
                f"Median rank move, sites kept in top {TOP}",
            ],
            rows,
        ),
    ]


if __name__ == "__main__":
    sys.exit(main())
