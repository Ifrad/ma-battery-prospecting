"""Load all sources for the pilot regions.

Usage: python -m prospect.ingest.run [region ...]   (default: all regions)
"""

import sys
from typing import NamedTuple

from prospect.db import connect
from prospect.ingest import arcgis
from prospect.ingest.client import Client
from prospect.ingest.sources import SOURCES
from prospect.regions import load_regions

URLS = {s.name: s.url for s in SOURCES}

# Loaded once for the whole state; the rest are loaded per pilot town.
STATEWIDE = [("utility_territories", "raw_utility_territories")]
PER_TOWN = [("parcels", "raw_parcels"), ("footprints", "raw_footprints")]


class Load(NamedTuple):
    region: str
    town: str
    source: str
    table: str
    scope: str


def plan(regions: dict[str, dict[int, str]]) -> list[Load]:
    loads = [Load("statewide", "", s, t, "1=1") for s, t in STATEWIDE]
    for region, towns in regions.items():
        for town_id, town in towns.items():
            for source, table in PER_TOWN:
                loads.append(Load(region, town, source, table, f"TOWN_ID={town_id}"))
    return loads


def main(names: list[str]) -> None:
    regions = load_regions()
    unknown = set(names) - set(regions)
    if unknown:
        raise SystemExit(f"unknown region {sorted(unknown)}; known: {sorted(regions)}")
    chosen = {n: t for n, t in regions.items() if not names or n in names}
    with connect(autocommit=True) as conn, Client() as client:
        for load in plan(chosen):
            result = arcgis.load(
                conn, client, load.source, URLS[load.source], load.table, load.scope
            )
            print(f"{load.region} {load.town} {load.source}: {result}")


if __name__ == "__main__":
    main(sys.argv[1:])
