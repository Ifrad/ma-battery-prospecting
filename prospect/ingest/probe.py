"""Fetch one small page from each source and print its fields. No database writes.

Usage: python -m prospect.ingest.probe [source ...]
"""

import sys

from prospect.ingest.client import Client
from prospect.ingest.sources import SOURCES, Source

SAMPLE_ROWS = 5


def probe_arcgis(client: Client, source: Source) -> dict:
    layer = client.get(source.url, params={"f": "json"}).json()
    count = client.get(
        f"{source.url}/query",
        params={"where": "1=1", "returnCountOnly": "true", "f": "json"},
    ).json()
    page = client.get(
        f"{source.url}/query",
        params={
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "false",
            "resultRecordCount": SAMPLE_ROWS,
            "f": "json",
        },
    ).json()
    for reply in (layer, count, page):
        if "error" in reply:
            raise RuntimeError(f"{source.name}: {reply['error']}")
    rows = [feature["attributes"] for feature in page["features"]]
    return {
        "name": source.name,
        "url": source.url,
        "rows": count["count"],
        "page_size": layer.get("maxRecordCount"),
        "geometry": layer.get("geometryType"),
        "fields": [
            (f["name"], f["type"].removeprefix("esriFieldType"))
            for f in layer["fields"]
        ],
        "sample": rows,
    }


def probe_ckan(client: Client, source: Source) -> dict:
    reply = client.get(
        source.url, params={"resource_id": source.resource_id, "limit": SAMPLE_ROWS}
    ).json()
    if not reply.get("success"):
        raise RuntimeError(f"{source.name}: {reply.get('error')}")
    result = reply["result"]
    fields = [(f["id"], f["type"]) for f in result["fields"] if f["id"] != "_id"]
    return {
        "name": source.name,
        "url": f"{source.url}?resource_id={source.resource_id}",
        "rows": result["total"],
        "page_size": None,
        "geometry": None,
        "fields": fields,
        "sample": result["records"],
    }


PROBES = {"arcgis": probe_arcgis, "ckan": probe_ckan}


def first_value(rows: list[dict], field: str):
    """First non-empty sample value for a field, to show what it looks like."""
    for row in rows:
        value = row.get(field)
        if value not in (None, ""):
            return value
    return None


def report(result: dict) -> str:
    lines = [
        f"## {result['name']}",
        f"url: {result['url']}",
        f"rows: {result['rows']}  page size: {result['page_size']}  "
        f"geometry: {result['geometry']}",
        "",
    ]
    for name, kind in result["fields"]:
        sample = first_value(result["sample"], name)
        lines.append(f"  {name:<45} {kind:<10} {str(sample)[:50]!s}")
    return "\n".join(lines)


def main(names: list[str]) -> None:
    chosen = [s for s in SOURCES if not names or s.name in names]
    with Client() as client:
        for source in chosen:
            print(report(PROBES[source.kind](client, source)), end="\n\n")


if __name__ == "__main__":
    main(sys.argv[1:])
