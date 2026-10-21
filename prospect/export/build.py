"""Write the per-region export files from the latest score run.

Usage: python -m prospect.export.build (make export)

For each region: export/<region>.geojson (one feature per scored site, both
scenarios) and export/<region>.csv (one row per site and scenario). Values
are simulated gross yearly revenue per battery block, before any host share:
not profit, not accurate, unvalidated. Reads the database only.
"""

import csv
import json
import subprocess
import sys
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

from prospect.db import connect
from prospect.model import grid
from prospect.model.report import rank_key
from prospect.model.run import config_hash
from prospect.priors import config

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "export"
REGIONS = ("metro_south", "worcester")
SCENARIOS = ("demand_savings", "with_connected_solutions")

SCORES = """
    SELECT s.*, st.owner, st.site_addr, initcap(u.attrs ->> 'TOWN') AS town,
           st.parcels AS parcel_count, st.buildings AS building_count,
           st.area_sqft, ST_X(st.geom) AS lon, ST_Y(st.geom) AS lat,
           f.profile, f.annual_kwh, f.peak_kw AS funnel_peak_kw
    FROM site_scores s
    JOIN sites st USING (site_id)
    JOIN site_funnel f USING (site_id)
    JOIN raw_utility_territories u ON (u.attrs ->> 'TOWN_ID')::integer = st.town_id
    WHERE s.run_id = %s
    ORDER BY s.site_id, s.scenario
"""
# Size-only rank: building area among every candidate site in the region, as
# the earlier public prototype ranked (docs/VALIDATION.md).
SIZE_RANK = """
    SELECT site_id, rank() OVER (PARTITION BY region ORDER BY area_sqft DESC)
    FROM site_evidence WHERE candidate AND region IS NOT NULL
"""
PARCELS = """
    SELECT p.site_id, p.loc_id, p.site_addr, p.use_code, p.use_desc, p.owner
    FROM parcels p WHERE p.site_id = ANY(%s) ORDER BY p.site_id, p.loc_id
"""
BUILDINGS = """
    SELECT site_id, building_id, round(area_sqft) AS area_sqft, area_source,
           electricity_source, round(grid_kwh) AS grid_kwh, segment
    FROM building_evidence WHERE candidate AND site_id = ANY(%s)
    ORDER BY site_id, building_id
"""


def latest_run(conn) -> dict:
    cur = conn.execute("SELECT * FROM score_runs ORDER BY run_id DESC LIMIT 1")
    return dict(zip([d.name for d in cur.description], cur.fetchone(), strict=True))


def fetch(conn, sql: str, params=None) -> list[dict]:
    cur = conn.execute(sql, params)
    names = [d.name for d in cur.description]
    return [dict(zip(names, r, strict=True)) for r in cur.fetchall()]


def scenario_block(r: dict) -> dict:
    """One scenario's results, rounded to whole dollars."""
    d = lambda x: round(float(x))  # noqa: E731
    return {
        "value_per_block": {k: d(r[f"value_{k}"]) for k in ("p10", "p50", "p90")},
        "total": {k: d(r[f"total_{k}"]) for k in ("p10", "p50", "p90")},
        "streams": {
            "demand_savings": {
                "p50": d(r["demand_p50"]),
                "share": round(r["demand_share"], 4),
            },
            "connected_solutions": {
                "p50": d(r["grid_p50"]),
                "share": round(r["grid_share"], 4),
            },
        },
        "top_drivers": r["top_drivers"],
    }


def draws_block(r: dict) -> dict:
    """Per draw, in physical units per block per year: kW-months of billed
    peak cut under G-2 and G-3 (realization factor applied), whole blocks,
    the drawn site peak in kW and whether the draw is billed on G-3."""
    if r["peak_kw"] is None:
        raise SystemExit("the latest score run has no peak draws; run make score")
    return {
        "kwm_g2": [round(float(v), 1) for v in r["kwm_g2"]],
        "kwm_g3": [round(float(v), 1) for v in r["kwm_g3"]],
        "blocks": [int(v) for v in r["blocks_draws"]],
        "peak_kw": [round(float(v), 1) for v in r["peak_kw"]],
        "g3": [int(v) for v in r["g3_draws"]],
    }


def sites(conn, run_id: int, cfg: dict) -> list[dict]:
    rows = fetch(conn, SCORES, (run_id,))
    size_rank = dict(conn.execute(SIZE_RANK).fetchall())
    by_site: dict[str, dict] = {}
    for r in rows:
        s = by_site.setdefault(
            r["site_id"],
            {
                "site_id": r["site_id"],
                "region": r["region"],
                "owner": r["owner"],
                "site_addr": r["site_addr"],
                "town": r["town"],
                "segment": r["segment"],
                "utility": r["utility"],
                "tier": r["tier"],
                "profile": r["profile"],
                "flags": [],
                "passes_200kw": r["passes_200kw"],
                "least_certain": r["least_certain"],
                "blocks": round(r["blocks"], 2),
                "area_sqft": round(r["area_sqft"]),
                "parcel_count": r["parcel_count"],
                "building_count": r["building_count"],
                "annual_kwh_estimate": round(r["annual_kwh"]),
                "size_rank": size_rank.get(r["site_id"]),
                "lon": round(r["lon"], 6),
                "lat": round(r["lat"], 6),
                "scenarios": {},
            },
        )
        s["flags"] = sorted(set(s["flags"]) | set(r["flags"]))
        s["scenarios"][r["scenario"]] = scenario_block(r)
        if r["scenario"] == "with_connected_solutions":
            s["draws"] = draws_block(r)
            s["event_window"] = grid.event_ratios({"profile": r["profile"]}, cfg)
    out = list(by_site.values())
    ids = [s["site_id"] for s in out]
    parcels, buildings = {}, {}
    for p in fetch(conn, PARCELS, (ids,)):
        parcels.setdefault(p.pop("site_id"), []).append(p)
    for b in fetch(conn, BUILDINGS, (ids,)):
        b["area_sqft"] = int(b["area_sqft"]) if b["area_sqft"] is not None else None
        b["grid_kwh"] = int(b["grid_kwh"]) if b["grid_kwh"] is not None else None
        buildings.setdefault(b.pop("site_id"), []).append(b)
    for s in out:
        s["parcels"] = parcels.get(s["site_id"], [])
        s["buildings"] = buildings.get(s["site_id"], [])
    for region in REGIONS:
        ranked = sorted(
            (s for s in out if s["region"] == region),
            key=lambda s: rank_key(
                {
                    "site_id": s["site_id"],
                    "value_p50": s["scenarios"]["with_connected_solutions"][
                        "value_per_block"
                    ]["p50"],
                    "blocks": s["blocks"],
                    "total_p50": s["scenarios"]["with_connected_solutions"]["total"][
                        "p50"
                    ],
                }
            ),
        )
        for i, s in enumerate(ranked, 1):
            s["model_rank"] = i
    return out


def geojson(region_sites: list[dict]) -> dict:
    features = []
    for s in sorted(region_sites, key=lambda s: s["model_rank"]):
        props = {k: v for k, v in s.items() if k not in ("lon", "lat")}
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [s["lon"], s["lat"]]},
                "properties": props,
            }
        )
    return {"type": "FeatureCollection", "features": features}


CSV_COLUMNS = [
    "model_rank",
    "size_rank",
    "site_id",
    "owner",
    "site_addr",
    "town",
    "segment",
    "tier",
    "utility",
    "flags",
    "scenario",
    "value_p10",
    "value_p50",
    "value_p90",
    "blocks",
    "total_p50",
    "demand_share",
    "connected_solutions_share",
    "lat",
    "lon",
]


def csv_rows(region_sites: list[dict]) -> list[dict]:
    rows = []
    for s in sorted(region_sites, key=lambda s: s["model_rank"]):
        for name in SCENARIOS:
            sc = s["scenarios"][name]
            rows.append(
                {
                    **{
                        k: s[k]
                        for k in (
                            "model_rank",
                            "size_rank",
                            "site_id",
                            "owner",
                            "site_addr",
                            "town",
                            "segment",
                            "tier",
                            "utility",
                            "blocks",
                            "lat",
                            "lon",
                        )
                    },
                    "flags": ";".join(s["flags"]),
                    "scenario": name,
                    **{
                        f"value_{k}": sc["value_per_block"][k]
                        for k in ("p10", "p50", "p90")
                    },
                    "total_p50": sc["total"]["p50"],
                    "demand_share": sc["streams"]["demand_savings"]["share"],
                    "connected_solutions_share": sc["streams"]["connected_solutions"][
                        "share"
                    ],
                }
            )
    return rows


def manifest(cfg: dict, every: list[dict]) -> dict:
    """The model inputs the report needs to recompute value per block,
    expected blocks and the stream split from the draws."""
    cs = cfg["connected_solutions"]
    block = cfg["battery"]["block"]
    utilities = sorted({s["utility"] for s in every})
    factor = lambda c: {"value": c["value"], **c.get("range", {})}  # noqa: E731
    return {
        "draws": cfg["model"]["draws"]["value"],
        "battery_block": {
            "power_kw": block["power_kw"],
            "energy_kwh": block["energy_kwh"],
        },
        "demand_rates_usd_per_kw_month": {
            u: {
                s["name"]: s["demand_charge_per_kw_month"]
                for s in cfg["rates"]["utilities"][u]["schedules"]
                if s["name"] in ("G-2", "G-3")
            }
            for u in utilities
        },
        "realization_factor": factor(cfg["profiles"]["realization_factor"]),
        "connected_solutions": {
            "usd_per_kw_season": cs["daily_dispatch_usd_per_kw_season"]["value"],
            "eligible_utilities": cs["eligible_utilities"]["value"],
            "performance_factor": factor(cs["performance_factor"]),
            "overlap_factor": factor(cs["overlap_factor"]),
            "site_exports": cs["site_exports"]["value"],
            "export_cap_share_of_site_peak": cs["export_cap_share_of_site_peak"][
                "value"
            ],
        },
        # The report matches a customer status file by owner name normalized
        # the same way sites are grouped (config/sites.yaml).
        "owner_drop_words": cfg["sites"]["owner_normalization"]["drop_words"],
        # and by address with the LBER address abbreviations.
        "address_words": cfg["sites"]["lber_match"]["address_words"],
        "placeholders": [
            {"file": f, "path": p, "value": v, "note": n}
            for f, p, v, n in config.placeholders(config.load_all())
        ],
    }


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def version() -> str:
    """The code version: git describe when run in a checkout, else the
    package version. It names the commit that produced the export, one
    behind the commit that holds it, and ends in -dirty only when tracked
    files outside export/ have changes: the export's own files never count."""
    try:
        described = git("describe", "--tags", "--always")
        changed = git(
            "status", "--porcelain", "--untracked-files=no", "--", ".", ":!export"
        )
    except (OSError, subprocess.CalledProcessError):
        return metadata.version("prospect")
    return described + ("-dirty" if changed else "")


def provenance(conn, run: dict, cfg: dict) -> dict:
    """Version, time, config hash and the sources behind the export. EnerNOC
    is left out on purpose: the tool does not incorporate it."""
    fetched = dict(
        conn.execute(
            "SELECT source, max(finished_at)::date::text FROM ingest_runs"
            " WHERE status = 'succeeded' AND source = ANY(%s) GROUP BY 1",
            (["parcels", "footprints", "utility_territories", "lber", "comstock"],),
        ).fetchall()
    )
    years = [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT reporting_year FROM raw_lber ORDER BY 1"
        ).fetchall()
    ]
    d = cfg["comstock"]["dataset"]
    return {
        "version": version(),
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "config_hash": run["config_hash"],
        "score_run": run["run_id"],
        "scored_at": run["scored_at"].isoformat(timespec="seconds"),
        "sources": {
            "lber_reporting_years": years,
            "comstock": {"release": d["release"], "weather_year": d["weather_year"]},
            "fetched": fetched,
            "rates_read": {
                u: str(v["read"])
                for u, v in cfg["rates"]["utilities"].items()
                if "read" in v
            },
        },
    }


def write(conn, out: Path = OUT) -> dict:
    run = latest_run(conn)
    if run["config_hash"] != config_hash():
        raise SystemExit(
            "config/ changed since the latest score run; run make score first"
        )
    out.mkdir(exist_ok=True)
    cfg = config.load()
    every = sites(conn, run["run_id"], cfg)
    written = {}
    for region in REGIONS:
        rs = [s for s in every if s["region"] == region]
        gj = out / f"{region}.geojson"
        gj.write_text(json.dumps(geojson(rs), separators=(",", ":")))
        with (out / f"{region}.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, CSV_COLUMNS)
            w.writeheader()
            w.writerows(csv_rows(rs))
        written[region] = len(rs)
    (out / "manifest.json").write_text(
        json.dumps({**provenance(conn, run, cfg), **manifest(cfg, every)}, indent=1)
    )
    return {"run_id": run["run_id"], "sites": written}


def main() -> int:
    with connect() as conn:
        out = write(conn)
    for region, n in out["sites"].items():
        print(f"export/{region}.geojson and .csv: {n} sites")
    return 0


if __name__ == "__main__":
    sys.exit(main())
