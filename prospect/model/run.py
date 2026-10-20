"""Score funnel survivors and store the results.

Usage: prospect score [--installed-cost X --min-host-benefit Y [--itc]]
       (make score runs it with no options)

With no options it scores every site in scope under each scenario, stores a
new run in score_runs and site_scores, and writes docs/SCORES.md. With an
installed cost and a minimum host benefit it reads the latest run instead
and prints model confidence per site, recomputed from the stored draws.
Values are simulated gross yearly revenue per block before any host share,
not profit, and unvalidated.
"""

import hashlib
from pathlib import Path

import numpy as np

from prospect.db import connect
from prospect.model import cost, report, score
from prospect.priors import config

ROOT = Path(__file__).resolve().parents[2]

# Scope: funnel survivors at the loosest reported peak line, both tiers.
SCOPE = """
    SELECT site_id, region, segment, utility, tier, profile, flags,
           dropped_by IS NULL AS passes_200kw
    FROM site_funnel
    WHERE (dropped_by IS NULL OR dropped_by = 'peak')
        AND peak_kw >= %(min_kw)s
    ORDER BY site_id
"""
BUILDINGS = """
    SELECT site_id, building_id, segment, electricity_source, grid_kwh,
           lber_confidence, area_sqft, area_source
    FROM building_evidence
    WHERE candidate AND site_id = ANY(%(ids)s)
    ORDER BY building_id
"""
COLUMNS = (
    "run_id, site_id, scenario, region, segment, utility, tier, passes_200kw,"
    " least_certain, flags, blocks, value_p10, value_p50, value_p90, total_p10,"
    " total_p50, total_p90, break_even_p50, break_even_p10, break_even_p50_itc,"
    " break_even_p10_itc, itc_applies, demand_p50, grid_p50, demand_share,"
    " grid_share, top_drivers, kwm_g2, kwm_g3, blocks_draws, grid_kw"
)


def config_hash() -> str:
    h = hashlib.sha256()
    for p in sorted((ROOT / "config").glob("*.yaml")):
        h.update(p.name.encode() + b"\0" + p.read_bytes())
    return h.hexdigest()


def load_scope(conn, cfg: dict) -> list[tuple[dict, list[dict]]]:
    min_kw = min(cfg["funnel"]["report_peak_kw"]["value"])
    cur = conn.execute(SCOPE, {"min_kw": min_kw})
    names = [d.name for d in cur.description]
    sites = [dict(zip(names, r, strict=True)) for r in cur.fetchall()]
    cur = conn.execute(BUILDINGS, {"ids": [s["site_id"] for s in sites]})
    names = [d.name for d in cur.description]
    by_site: dict[str, list[dict]] = {}
    for r in cur.fetchall():
        b = dict(zip(names, r, strict=True))
        by_site.setdefault(b.pop("site_id"), []).append(b)
    return [(s, by_site[s["site_id"]]) for s in sites]


def row(run_id: int, site: dict, r: dict) -> list:
    v, t, be, st, x = (
        r["value_per_block"],
        r["total"],
        r["break_even"],
        r["streams"],
        r["draws"],
    )
    return [
        run_id,
        site["site_id"],
        r["scenario"],
        site["region"],
        site["segment"],
        site["utility"],
        site["tier"],
        site["passes_200kw"],
        "no_open_profile" in site["flags"],
        site["flags"],
        r["blocks"],
        v["p10"],
        v["p50"],
        v["p90"],
        t["p10"],
        t["p50"],
        t["p90"],
        be["p50"],
        be["p10"],
        be["p50_itc"],
        be["p10_itc"],
        be["itc_applies"],
        st["demand"]["p50"],
        st["connected_solutions"]["p50"],
        st["demand"]["share"],
        st["connected_solutions"]["share"],
        [f"{name} {rho:+.2f}" for name, rho in r["drivers"]],
        x["kwm_g2"].astype(np.float32).tolist(),
        x["kwm_g3"].astype(np.float32).tolist(),
        x["blocks"].astype(int).tolist(),
        float(x["grid_kw"][0]),
    ]


def score_all(conn, cfg: dict) -> int:
    """Score every site in scope, store a new run, return its run id."""
    run_id = conn.execute(
        "INSERT INTO score_runs (config_hash, draws) VALUES (%s, %s) RETURNING run_id",
        (config_hash(), cfg["model"]["draws"]["value"]),
    ).fetchone()[0]
    # Load the scope before COPY starts: no other query can run on this
    # connection while a COPY is in progress.
    scope = load_scope(conn, cfg)
    with conn.cursor().copy(f"COPY site_scores ({COLUMNS}) FROM STDIN") as copy:
        for site, buildings in scope:
            for r in score.score_site(site, buildings, cfg):
                copy.write_row(row(run_id, site, r))
    return run_id


def value_draws(stored: dict, cfg: dict) -> np.ndarray:
    """Value per block per draw, repriced from the stored physical units."""
    rates = {
        s["name"]: s["demand_charge_per_kw_month"]
        for s in cfg["rates"]["utilities"][stored["utility"]]["schedules"]
    }
    demand = np.asarray(stored["kwm_g2"]) * rates["G-2"] + np.asarray(
        stored["kwm_g3"]
    ) * rates.get("G-3", 0.0)
    grid = (
        stored["grid_kw"]
        * cfg["connected_solutions"]["daily_dispatch_usd_per_kw_season"]["value"]
    )
    return demand + (grid if stored["scenario"] == "with_connected_solutions" else 0.0)


def confidence_rows(conn, cfg: dict, installed: float, host: float, itc: bool):
    """Model confidence per site and scenario of the latest run."""
    cur = conn.execute(
        "SELECT site_id, scenario, utility, blocks, kwm_g2, kwm_g3, grid_kw"
        " FROM site_scores WHERE run_id = (SELECT max(run_id) FROM score_runs)"
        " ORDER BY site_id, scenario"
    )
    names = [d.name for d in cur.description]
    for r in cur.fetchall():
        s = dict(zip(names, r, strict=True))
        yield (
            s["site_id"],
            s["scenario"],
            cost.confidence(
                value_draws(s, cfg), installed, host, cfg, itc, s["blocks"]
            ),
        )


def main(installed: float | None, host: float | None, itc: bool) -> int:
    cfg = config.load()
    if (installed is None) != (host is None):
        print("give both --installed-cost and --min-host-benefit, or neither")
        return 2
    with connect() as conn:
        if installed is not None:
            print("site_id,scenario,model_confidence")
            for site_id, scenario, c in confidence_rows(
                conn, cfg, installed, host, itc
            ):
                print(f"{site_id},{scenario},{c:.3f}")
            return 0
        run_id = score_all(conn, cfg)
        conn.commit()
        report.write(conn, run_id, cfg)
    print(f"score run {run_id}; wrote docs/SCORES.md")
    return 0
