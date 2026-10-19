"""Load all sources for the pilot regions.

Usage: python -m prospect.ingest.run [region ...]   (default: all regions)
"""

import sys

from prospect.db import connect
from prospect.ingest import arcgis
from prospect.ingest.client import Client
from prospect.ingest.sources import SOURCES
from prospect.regions import load_regions

URLS = {s.name: s.url for s in SOURCES}


def main(names: list[str]) -> None:
    regions = load_regions()
    chosen = {n: t for n, t in regions.items() if not names or n in names}
    if names and len(chosen) != len(names):
        raise SystemExit(f"unknown region in {names}; known: {sorted(regions)}")
    with connect(autocommit=True) as conn, Client() as client:
        for region, towns in chosen.items():
            for town_id, town in towns.items():
                result = arcgis.load(
                    conn,
                    client,
                    "parcels",
                    URLS["parcels"],
                    "raw_parcels",
                    f"TOWN_ID={town_id}",
                )
                print(f"{region} {town} parcels: {result}")


if __name__ == "__main__":
    main(sys.argv[1:])
