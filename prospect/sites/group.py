"""Group parcels into outreach sites by touching parcels and normalized owner."""

import re
from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parents[2] / "config" / "sites.yaml"


def load_config(path: Path = CONFIG) -> dict:
    return yaml.safe_load(path.read_text())


def normalize_owner(name: str | None, truncated: bool, drop_words) -> str | None:
    """Owner name for matching: upper case, no punctuation or company words.

    A possibly cut-off name loses its last word, which may be partial.
    """
    tokens = re.sub(r"[^A-Z0-9]+", " ", (name or "").upper()).split()
    if truncated:
        tokens = tokens[:-1]
    tokens = [t for t in tokens if t not in set(drop_words)]
    return " ".join(tokens) or None


def components(nodes, edges) -> dict:
    """Map each node to its group's smallest node, given undirected edges."""
    parent = {n: n for n in nodes}

    def find(n):
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n

    for a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    return {n: find(n) for n in nodes}


# Pairs of touching parcels in one town whose owners match: equal normalized
# names, or a possibly cut-off name that is a whole-word prefix of the other.
# Distance is planar, in Massachusetts State Plane meters (EPSG:26986).
# Geography ST_DWithin is not used: on PostGIS 3.5.2 it returned true for
# 168 pilot pairs 3 to 315 m apart, and its answers varied between runs.
TOUCHING_SAME_OWNER = """
SELECT a.loc_id, b.loc_id
FROM parcels a
JOIN parcels b
    ON a.town_id = b.town_id
    AND a.loc_id < b.loc_id
    AND a.geom && ST_Expand(b.geom, %(tol_deg)s)
WHERE a.owner_norm IS NOT NULL AND b.owner_norm IS NOT NULL
    AND (
        a.owner_norm = b.owner_norm
        OR (a.owner_truncated AND starts_with(b.owner_norm || ' ', a.owner_norm || ' '))
        OR (b.owner_truncated AND starts_with(a.owner_norm || ' ', b.owner_norm || ' '))
    )
    AND ST_DWithin(ST_Transform(a.geom, 26986), ST_Transform(b.geom, 26986), %(tol_m)s)
"""


def group(conn, config: dict) -> None:
    """Fill parcels.owner_norm, owner_truncated and site_id.

    A name is possibly cut off when it is within cutoff_within_chars of
    the longest owner name in its town: a name cut at the field width
    loses its trailing space too.
    """
    drop = config["owner_normalization"]["drop_words"]
    rows = conn.execute(
        "SELECT p.loc_id, p.owner, length(p.owner) >= m.width - %s"
        " FROM parcels p JOIN (SELECT town_id, max(length(owner)) AS width"
        " FROM parcels GROUP BY town_id) m USING (town_id)",
        (config["owner_normalization"]["cutoff_within_chars"],),
    ).fetchall()
    conn.execute(
        "CREATE TEMP TABLE parcel_owner (loc_id text, owner_norm text,"
        " owner_truncated boolean, site_id text) ON COMMIT DROP"
    )
    names = [
        (loc, normalize_owner(owner, bool(cut), drop), bool(cut))
        for loc, owner, cut in rows
    ]
    with conn.cursor().copy(
        "COPY parcel_owner (loc_id, owner_norm, owner_truncated) FROM STDIN"
    ) as copy:
        for row in names:
            copy.write_row(row)
    conn.execute(
        "UPDATE parcels p SET owner_norm = o.owner_norm,"
        " owner_truncated = o.owner_truncated"
        " FROM parcel_owner o WHERE o.loc_id = p.loc_id"
    )
    tol_m = config["touch_tolerance_m"]["value"]
    # Degrees to search before the exact distance check; generous at 42 N.
    edges = conn.execute(
        TOUCHING_SAME_OWNER, {"tol_m": tol_m, "tol_deg": tol_m / 50_000}
    ).fetchall()
    site_of = components([loc for loc, _, _ in names], edges)
    conn.execute("TRUNCATE parcel_owner")
    with conn.cursor().copy("COPY parcel_owner (loc_id, site_id) FROM STDIN") as copy:
        for loc, site in site_of.items():
            copy.write_row((loc, site))
    conn.execute(
        "UPDATE parcels p SET site_id = o.site_id"
        " FROM parcel_owner o WHERE o.loc_id = p.loc_id"
    )
