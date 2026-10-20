"""Count candidate sites through the prospecting funnel.

Usage: python -m prospect.priors.funnel

Reads the database and config only. Rebuilds the site_funnel table, one row
per candidate site, and writes docs/FUNNEL.md. Filters run in order:
eligible utility, estimated monthly use, estimated peak. A dropped site
stays in the table with the filter that dropped it. Rerun after make sites.
"""

import math
import sys
from collections import Counter
from pathlib import Path

from prospect.db import connect
from prospect.priors import config

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs" / "FUNNEL.md"
REGIONS = {"metro_south": "Metro South", "worcester": "Worcester"}
STAGES = ["candidate", "utility", "kwh", "peak"]
STAGE_LABEL = {
    "candidate": "Candidate sites",
    "utility": "1. ConnectedSolutions utility",
    "kwh": "2. Over the monthly kWh line",
    "peak": "3. Estimated peak over the kW line",
}


def profile(site: dict, buildings: list[dict], cfg: dict) -> tuple[str, float, list]:
    """(profile name, load factor, flags) for one site."""
    prof, sim = cfg["profiles"], cfg["simulation"]
    pooled_lf = sim["pooled"]["load_factor"]["median"]
    main = max(buildings, key=lambda b: b["area_sqft"] or 0)
    no_profile = prof["no_open_profile"]
    if (
        site["segment"] in no_profile["segments"]
        or main["use_code"] in no_profile["use_codes"]
    ):
        return "no open profile", pooled_lf, ["no_open_profile"]
    types = prof["comstock_types"]["segments"].get(site["segment"])
    if types is None and site["segment"] == "generic":
        types = prof["comstock_types"]["generic_use_codes"].get(main["use_code"])
    if not types:
        return "placeholder mix", pooled_lf, ["placeholder_mix"]
    area = sum(b["area_sqft"] or 0 for b in buildings) or 1.0
    best = min(
        types,
        key=lambda t: abs(
            math.log(area) - math.log(sim["types"][t]["floor_area_median_sqft"])
        ),
    )
    return best, sim["types"][best]["load_factor"]["median"], []


def evaluate(site: dict, buildings: list[dict], cfg: dict) -> dict:
    """One site's funnel row: estimates, tier, flags and the filter it fails."""
    priors = cfg["intensity"]["segments"]
    flags = []
    total = measured = 0.0
    usable = True
    for b in buildings:
        if b["electricity_source"] == "measured" and b["grid_kwh"]:
            total += b["grid_kwh"]
            measured += b["grid_kwh"]
            continue
        prior = priors.get(b["segment"], {}).get("prior", {}).get("median")
        if prior is None or not b["area_sqft"]:
            usable = False
            continue
        total += prior * b["area_sqft"]
        source = priors[b["segment"]]["prior_from"]
        if source != "pilot measured, our area":
            flags.append(f"intensity: {source}")
    name, lf, pflags = profile(site, buildings, cfg)
    flags += pflags
    eligible = (
        site["utility"] in cfg["connected_solutions"]["eligible_utilities"]["value"]
    )
    if not eligible and site["utility_flag"] == "municipal":
        flags.append("municipal_plant")
    if site["utility"] == "Eversource Energy (NSTAR Electric)":
        flags.append("eversource_all_hours")
    annual = total if usable and total > 0 else None
    peak = annual / 8760 / lf if annual else None
    funnel = cfg["funnel"]
    if not eligible:
        dropped = "utility"
    elif annual is None:
        dropped = "no_estimate"
    elif annual / 12 <= funnel["min_kwh_per_month"]["value"]:
        dropped = "kwh"
    elif peak < funnel["min_peak_kw"]["value"]:
        dropped = "peak"
    else:
        dropped = None
    return {
        "site_id": site["site_id"],
        "region": site["region"],
        "segment": site["segment"],
        "utility": site["utility"],
        "tier": 1 if measured > 0 else 2,
        "measured_share": measured / total if total else 0.0,
        "annual_kwh": annual,
        "kwh_per_month": annual / 12 if annual else None,
        "profile": name,
        "load_factor": lf,
        "peak_kw": peak,
        "dropped_by": dropped,
        "flags": sorted(set(flags)),
    }


def passed(row: dict, stage: str) -> bool:
    """Whether a site survives up to and including a stage."""
    order = {"utility": 1, "no_estimate": 2, "kwh": 2, "peak": 3}
    reached = order[row["dropped_by"]] - 1 if row["dropped_by"] else 3
    return STAGES.index(stage) <= reached


def load_inputs(conn) -> list[tuple[dict, list[dict]]]:
    rows = conn.execute(
        """
        SELECT s.site_id, s.region, s.segment, s.utility, s.utility_flag,
               b.segment, b.electricity_source, b.grid_kwh, b.area_sqft,
               left(p.use_code, 3)
        FROM site_evidence s
        JOIN building_evidence b USING (site_id)
        LEFT JOIN parcels p ON p.loc_id = b.loc_id
        WHERE s.candidate AND b.candidate
        ORDER BY s.site_id
        """
    ).fetchall()
    sites: dict[str, tuple[dict, list[dict]]] = {}
    for sid, region, seg, util, uflag, bseg, src, kwh, area, code in rows:
        site, buildings = sites.setdefault(
            sid,
            (
                {
                    "site_id": sid,
                    "region": region,
                    "segment": seg,
                    "utility": util,
                    "utility_flag": uflag,
                },
                [],
            ),
        )
        buildings.append(
            {
                "segment": bseg,
                "electricity_source": src,
                "grid_kwh": kwh,
                "area_sqft": area,
                "use_code": code,
            }
        )
    return list(sites.values())


def store(conn, rows: list[dict]) -> None:
    conn.execute("TRUNCATE site_funnel")
    cols = list(rows[0])
    with conn.cursor().copy(f"COPY site_funnel ({', '.join(cols)}) FROM STDIN") as copy:
        for r in rows:
            copy.write_row([r[c] for c in cols])


def table(header: list[str], rows: list[list]) -> str:
    def cell(v):
        return f"{v:,}" if isinstance(v, int) else str(v)

    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


def report(rows: list[dict], cfg: dict) -> str:
    f = cfg["funnel"]
    kwh_line = f["min_kwh_per_month"]["value"]
    kw_line = f["min_peak_kw"]["value"]

    def counts(key):
        groups = sorted({r[key] for r in rows if r[key]})
        return [
            [
                STAGE_LABEL[s],
                *[sum(passed(r, s) for r in rows if r[key] == g) for g in groups],
                sum(passed(r, s) for r in rows),
            ]
            for s in STAGES
        ], groups

    by_region, regions = counts("region")
    by_segment, segments = counts("segment")
    survivors = [r for r in rows if r["dropped_by"] is None]
    reached_peak = [r for r in rows if passed(r, "kwh")]
    no_estimate = sum(r["dropped_by"] == "no_estimate" for r in rows)
    municipal = sum("municipal_plant" in r["flags"] for r in rows)
    unpriced = {
        name for name, u in cfg["rates"]["utilities"].items() if "schedules" not in u
    }
    no_schedule = sum(r["utility"] in unpriced for r in rows)
    flag_counts = Counter(fl for r in survivors for fl in r["flags"])
    out = [
        "# Funnel",
        "",
        "Generated by `make funnel` from the database and config. Rerun it after"
        " `make sites`.",
        "",
        "Candidate sites that survive each filter, in order. A site dropped by a"
        " filter stays in the `site_funnel` table with the filter that dropped"
        " it; nothing is deleted. Survivors still carry unvalidated peak shape:"
        " their peak is estimated from yearly kWh and a simulated load factor,"
        " not measured.",
        "",
        f"1. The utility runs ConnectedSolutions (config/connected_solutions.yaml)."
        f" {municipal:,} sites served by municipal light plants are dropped here,"
        f" flagged municipal_plant; {no_schedule:,} of them are in the five towns"
        " whose plants publish no rate schedule (config/rates.yaml).",
        f"2. Estimated use above {kwh_line:,} kWh a month, the National Grid G-1"
        " line: LBER measured kWh where a building has it, otherwise floor area"
        " times the segment's median intensity (config/intensity.yaml).",
        f"3. Estimated peak at least {kw_line:,} kW: average kW from yearly kWh,"
        " divided by the median monthly load factor of the site's simulated"
        " type (config/simulation.yaml). Sites with no open profile or an"
        " unmapped use code take the pooled median and are flagged.",
        "",
        "Thresholds are placeholders in config/funnel.yaml.",
        "",
        "## By region",
        "",
        table(["Stage", *[REGIONS[g] for g in regions], "Both"], by_region),
        "",
        "## By segment",
        "",
        table(["Stage", *segments, "All"], by_segment),
        "",
        "## Peak line",
        "",
        "Sites past filter 2 with an estimated peak at or above each line:",
        "",
        table(
            ["Peak line", "Sites", "Tier 1", "Tier 2"],
            [
                [
                    f"{kw:,} kW" + (" (used)" if kw == kw_line else ""),
                    sum(r["peak_kw"] >= kw for r in reached_peak),
                    sum(r["peak_kw"] >= kw and r["tier"] == 1 for r in reached_peak),
                    sum(r["peak_kw"] >= kw and r["tier"] == 2 for r in reached_peak),
                ]
                for kw in f["report_peak_kw"]["value"]
            ],
        ),
        "",
        "## Survivors",
        "",
        f"{len(survivors):,} sites pass all three filters:"
        f" {sum(r['tier'] == 1 for r in survivors):,} in tier 1 (at least one"
        " building with LBER measured electricity) and"
        f" {sum(r['tier'] == 2 for r in survivors):,} in tier 2 (estimated only,"
        f" flagged). Sites with no usable estimate: {no_estimate:,}.",
        "",
        "Flags among survivors:",
        "",
        table(["Flag", "Sites"], [[k, v] for k, v in sorted(flag_counts.items())])
        if flag_counts
        else "None.",
        "",
        "Spikiness is not a filter. It is scored in Phase 4.",
    ]
    return "\n".join(out) + "\n"


def main() -> int:
    configs = config.load()
    with connect() as conn:
        rows = [evaluate(s, b, configs) for s, b in load_inputs(conn)]
        store(conn, rows)
        conn.commit()
    REPORT.write_text(report(rows, configs))
    print(f"site_funnel: {len(rows):,} rows; wrote {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
