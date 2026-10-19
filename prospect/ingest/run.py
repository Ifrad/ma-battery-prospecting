"""Load all sources for the pilot regions.

Usage: python -m prospect.ingest.run [region ...]   (default: all regions)
"""

import sys
from typing import NamedTuple

from prospect.db import connect
from prospect.ingest import arcgis
from prospect.ingest.client import Client
from prospect.ingest.sources import LBER, SOURCES
from prospect.regions import load_regions

URLS = {s.name: s.url for s in SOURCES}

# Loaded once for the whole state, with any constant columns; the rest are
# loaded per pilot town. LBER is statewide because validation is statewide.
STATEWIDE = [
    ("utility_territories", "raw_utility_territories", None),
    ("lber", "raw_lber", {"reporting_year": LBER["reporting_year"]}),
]
PER_TOWN = [("parcels", "raw_parcels"), ("footprints", "raw_footprints")]


class Load(NamedTuple):
    region: str
    town: str
    source: str
    table: str
    scope: str
    extra: dict | None = None


def plan(regions: dict[str, dict[int, str]]) -> list[Load]:
    loads = [Load("statewide", "", s, t, "1=1", e) for s, t, e in STATEWIDE]
    for region, towns in regions.items():
        for town_id, town in towns.items():
            for source, table in PER_TOWN:
                loads.append(Load(region, town, source, table, f"TOWN_ID={town_id}"))
    return loads


def summarize(outcomes: list[tuple[Load, dict | Exception]]) -> str:
    """Rows per region and source, then any count mismatches and failures."""
    totals: dict[tuple[str, str], list[int]] = {}
    mismatches, failures = [], []
    for load, outcome in outcomes:
        name = f"{load.region} {load.town} {load.source}".replace("  ", " ")
        if isinstance(outcome, Exception):
            failures.append(f"  {name}: {type(outcome).__name__}: {outcome}")
            continue
        total = totals.setdefault((load.region, load.source), [0, 0, 0])
        total[0] += 1
        total[1] += outcome["rows"]
        total[2] += outcome["source_rows"]
        if outcome["rows"] != outcome["source_rows"]:
            mismatches.append(
                f"  {name}: loaded {outcome['rows']}, source has "
                f"{outcome['source_rows']}"
            )
    lines = [f"{'region':<12} {'source':<20} {'loads':>5} {'rows':>9} {'source':>9}"]
    for (region, source), (loads, rows, source_rows) in totals.items():
        lines.append(
            f"{region:<12} {source:<20} {loads:>5} {rows:>9,} {source_rows:>9,}"
        )
    lines.append(f"\nCount mismatches: {len(mismatches)}")
    lines += mismatches
    lines.append(f"Failures: {len(failures)}")
    lines += failures
    return "\n".join(lines)


def main(names: list[str]) -> int:
    regions = load_regions()
    unknown = set(names) - set(regions)
    if unknown:
        raise SystemExit(f"unknown region {sorted(unknown)}; known: {sorted(regions)}")
    chosen = {n: t for n, t in regions.items() if not names or n in names}
    outcomes = []
    with connect(autocommit=True) as conn, Client() as client:
        for load in plan(chosen):
            try:
                outcome = arcgis.load(
                    conn,
                    client,
                    load.source,
                    URLS[load.source],
                    load.table,
                    load.scope,
                    load.extra,
                )
                print(f"{load.region} {load.town} {load.source}: {outcome['rows']}")
            except Exception as exc:  # recorded in ingest_runs; keep going
                outcome = exc
                print(f"{load.region} {load.town} {load.source}: FAILED {exc}")
            outcomes.append((load, outcome))
    print("\n" + summarize(outcomes))
    return 1 if any(isinstance(o, Exception) for _, o in outcomes) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
