"""Schema and size checks for the export files (no schema library)."""

from pathlib import Path

MAX_BYTES = 5_000_000  # CLAUDE.md: each committed export file at most 5 MB
SITE_FIELDS = {
    "site_id": str,
    "region": str,
    "owner": (str, type(None)),
    "site_addr": (str, type(None)),
    "town": str,
    "segment": str,
    "utility": str,
    "tier": int,
    "profile": str,
    "flags": list,
    "passes_200kw": bool,
    "least_certain": bool,
    "blocks": (int, float),
    "size_rank": int,
    "model_rank": int,
    "scenarios": dict,
    "draws": dict,
    "event_window": dict,
    "parcels": list,
    "buildings": list,
}
SCENARIOS = ("demand_savings", "with_connected_solutions")
DRAWS = ("kwm_g2", "kwm_g3", "blocks", "peak_kw", "g3")


def check_site(p: dict, draws: int) -> list[str]:
    out = []
    sid = p.get("site_id", "?")
    for k, t in SITE_FIELDS.items():
        if k not in p:
            out.append(f"{sid}: missing {k}")
        elif not isinstance(p[k], t):
            out.append(f"{sid}: {k} is {type(p[k]).__name__}")
    for s in SCENARIOS:
        sc = p.get("scenarios", {}).get(s)
        if sc is None:
            out.append(f"{sid}: missing scenario {s}")
            continue
        v = sc["value_per_block"]
        if not v["p10"] <= v["p50"] <= v["p90"]:
            out.append(f"{sid}: {s} percentiles out of order")
    for k in DRAWS:
        if len(p.get("draws", {}).get(k, [])) != draws:
            out.append(f"{sid}: draws.{k} does not have {draws} values")
    return out


def check(geojson: dict, manifest: dict) -> list[str]:
    if geojson.get("type") != "FeatureCollection":
        return ["not a FeatureCollection"]
    out = []
    for f in geojson["features"]:
        if f["geometry"]["type"] != "Point" or len(f["geometry"]["coordinates"]) != 2:
            out.append(f"{f['properties'].get('site_id')}: geometry is not a point")
        out += check_site(f["properties"], manifest["draws"])
    ranks = sorted(f["properties"]["model_rank"] for f in geojson["features"])
    if ranks != list(range(1, len(ranks) + 1)):
        out.append("model ranks are not 1 to n")
    return out


def too_large(directory: Path) -> list[str]:
    return [
        f"{p.name} is {p.stat().st_size:,} bytes"
        for p in sorted(directory.iterdir())
        if p.is_file() and p.stat().st_size > MAX_BYTES
    ]


MANIFEST_FIELDS = (
    "version",
    "generated_at",
    "config_hash",
    "score_run",
    "scored_at",
    "sources",
    "draws",
    "battery_block",
    "demand_rates_usd_per_kw_month",
    "realization_factor",
    "connected_solutions",
    "owner_drop_words",
    "address_words",
    "placeholders",
)


def check_manifest(m: dict) -> list[str]:
    out = [f"manifest: missing {k}" for k in MANIFEST_FIELDS if k not in m]
    if "sources" in m and not m["sources"].get("lber_reporting_years"):
        out.append("manifest: no LBER reporting year")
    if "costs" in m:
        out.append("manifest: carries a cost block; cost is not modeled")
    return out
