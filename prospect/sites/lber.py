"""Match pilot LBER buildings to footprints, and mark measured electricity.

Methods run in order and each LBER row (reporting year plus object id) stops
at the first that finds a building: exact UBID, point inside a footprint,
point inside a parcel, normalized address. Several candidates mean the
largest footprint is used and the confidence reads "ambiguous, n buildings".
"""

import re

PILOT_LBER = """
CREATE TEMP TABLE pilot_lber ON COMMIT DROP AS
SELECT l.reporting_year, l.objectid, l.geom, l.grid_kwh,
       trim(l.attrs->>'UBID') AS ubid,
       l.attrs->>'Street_Address' AS street_address,
       l.attrs->>'City' AS city,
       t.town_id, t.region
FROM raw_lber l
JOIN raw_utility_territories u ON ST_Contains(u.geom, l.geom)
JOIN pilot_towns t ON t.town_id = (u.attrs->>'TOWN_ID')::integer
"""

# {candidates} yields (reporting_year, objectid, building_id) for unmatched
# pilot rows; the first row per LBER row by footprint size is kept.
MATCH = """
INSERT INTO lber_matches (
    reporting_year, objectid, town_id, region, building_id, method,
    confidence, candidates, grid_kwh
)
SELECT DISTINCT ON (p.reporting_year, p.objectid)
    p.reporting_year, p.objectid, p.town_id, p.region, c.building_id,
    %(method)s,
    CASE WHEN c.n = 1 THEN %(label)s ELSE 'ambiguous, ' || c.n || ' buildings' END,
    c.n, p.grid_kwh
FROM pilot_lber p
JOIN (
    SELECT x.*, count(*) OVER (PARTITION BY x.reporting_year, x.objectid) AS n
    FROM ({candidates}) x
) c USING (reporting_year, objectid)
JOIN buildings b ON b.building_id = c.building_id
WHERE NOT EXISTS (
    SELECT 1 FROM lber_matches m
    WHERE m.reporting_year = p.reporting_year AND m.objectid = p.objectid
)
ORDER BY p.reporting_year, p.objectid, b.footprint_sqft DESC, b.building_id
"""

CANDIDATES = {
    "ubid": """
        SELECT p.reporting_year, p.objectid, b.building_id
        FROM pilot_lber p JOIN buildings b ON b.ubid = p.ubid""",
    "point_in_footprint": """
        SELECT p.reporting_year, p.objectid, b.building_id
        FROM pilot_lber p JOIN buildings b ON ST_Contains(b.geom, p.geom)""",
    "point_in_parcel": """
        SELECT DISTINCT p.reporting_year, p.objectid, b.building_id
        FROM pilot_lber p
        JOIN parcels pa ON ST_Contains(pa.geom, p.geom)
        JOIN buildings b ON b.loc_id = pa.loc_id""",
}


def normalize_address(text: str | None, words: dict) -> str | None:
    """Upper case, punctuation removed, street words shortened."""
    tokens = re.sub(r"[^A-Z0-9]+", " ", (text or "").upper()).split()
    return " ".join(words.get(t, t) for t in tokens) or None


def match_addresses(conn, config: dict) -> None:
    """Last method: normalized address equal to a parcel's, in the same town."""
    words = config["address_words"]
    label = config["confidence"]["address"]
    pending = conn.execute(
        "SELECT reporting_year, objectid, town_id, region, street_address, grid_kwh"
        " FROM pilot_lber p WHERE NOT EXISTS (SELECT 1 FROM lber_matches m"
        " WHERE m.reporting_year = p.reporting_year AND m.objectid = p.objectid)"
    ).fetchall()
    towns = {row[2] for row in pending}
    if not towns:
        return
    by_address: dict[tuple, list] = {}
    for town, addr, building_id, sqft in conn.execute(
        "SELECT pa.town_id, pa.site_addr, b.building_id, b.footprint_sqft"
        " FROM parcels pa JOIN buildings b USING (loc_id)"
        " WHERE pa.town_id = ANY(%s)",
        (list(towns),),
    ):
        key = (town, normalize_address(addr, words))
        by_address.setdefault(key, []).append((sqft, building_id))
    rows = []
    for year, oid, town, region, street, kwh in pending:
        address = normalize_address(street, words)
        found = by_address.get((town, address)) if address else None
        if not found:
            continue
        n = len(found)
        building_id = max(found)[1]
        confidence = label if n == 1 else f"ambiguous, {n} buildings"
        rows.append((year, oid, town, region, building_id, confidence, n, kwh))
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO lber_matches (reporting_year, objectid, town_id, region,"
            " building_id, method, confidence, candidates, grid_kwh)"
            " VALUES (%s, %s, %s, %s, %s, 'address', %s, %s, %s)",
            rows,
        )


UNMATCHED = """
INSERT INTO lber_unmatched (
    reporting_year, objectid, town_id, region, street_address, city, reason
)
SELECT p.reporting_year, p.objectid, p.town_id, p.region, p.street_address, p.city,
    CASE
        WHEN EXISTS (SELECT 1 FROM parcels pa WHERE ST_Contains(pa.geom, p.geom))
        THEN 'parcel has no building, no address match'
        ELSE 'outside parcels, no address match'
    END
FROM pilot_lber p
WHERE NOT EXISTS (
    SELECT 1 FROM lber_matches m
    WHERE m.reporting_year = p.reporting_year AND m.objectid = p.objectid
)
"""

# A building is measured from the latest reporting year in which a matched
# LBER row has grid electricity. Several rows in that year are summed and
# counted in lber_rows.
ELECTRICITY = """
UPDATE buildings b
SET electricity_source = 'measured', grid_kwh = m.kwh,
    grid_kwh_year = m.reporting_year, lber_rows = m.rows
FROM (
    SELECT DISTINCT ON (building_id) building_id, reporting_year,
        sum(grid_kwh) AS kwh, count(*) AS rows
    FROM lber_matches
    WHERE grid_kwh IS NOT NULL
    GROUP BY building_id, reporting_year
    ORDER BY building_id, reporting_year DESC
) m
WHERE m.building_id = b.building_id
"""


def match(conn, config: dict) -> None:
    conn.execute("TRUNCATE lber_matches, lber_unmatched")
    conn.execute(PILOT_LBER)
    labels = config["confidence"]
    for method, candidates in CANDIDATES.items():
        conn.execute(
            MATCH.format(candidates=candidates),
            {"method": method, "label": labels[method]},
        )
    match_addresses(conn, config)
    conn.execute(UNMATCHED)
    conn.execute(ELECTRICITY)
