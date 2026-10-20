"""Build the parcel, building and site tables from the raw tables.

Usage: python -m prospect.sites.build

Each run rebuilds everything in one transaction, from the SQL files in
sql/sites/ and the Python steps listed in STEPS, so it can be rerun at any
time.
"""

from pathlib import Path

from prospect import use_codes
from prospect.db import connect
from prospect.regions import load_regions
from prospect.sites import group, lber, owner, segments, ubid

SQL = Path(__file__).resolve().parents[2] / "sql" / "sites"

# In order. A string is a file in sql/sites/, a function takes the connection.
STEPS = [
    "01_parcels.sql",
    "02_buildings.sql",
    lambda conn: fill_ubids(conn),
    lambda conn: group.group(conn, group.load_config()),
    "03_sites.sql",
    lambda conn: lber.match(conn, group.load_config()["lber_match"]),
    "04_utility.sql",
    lambda conn: segments.assign(conn, segments.load_config()),
    "05_segments.sql",
    lambda conn: owner.assign(conn, group.load_config()),
    "06_owner_tenure.sql",
]


def fill_use_code_classes(conn, config: dict) -> None:
    conn.execute("TRUNCATE use_code_classes")
    pairs = conn.execute(
        "SELECT DISTINCT (attrs->>'TOWN_ID')::integer, attrs->>'USE_CODE'"
        " FROM raw_parcels WHERE attrs->>'USE_CODE' IS NOT NULL"
    ).fetchall()
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO use_code_classes (town_id, use_code, use_class)"
            " VALUES (%s, %s, %s)",
            [(t, c, use_codes.classify(c, t, config)) for t, c in pairs],
        )


def fill_pilot_towns(conn, regions: dict) -> None:
    conn.execute("TRUNCATE pilot_towns")
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO pilot_towns (town_id, region) VALUES (%s, %s)",
            [(t, r) for r, towns in regions.items() for t in towns],
        )


def fill_ubids(conn) -> None:
    """Set buildings.ubid from each footprint's bounding box and centroid."""
    rows = conn.execute(
        "SELECT building_id, ST_YMin(geom), ST_XMin(geom), ST_YMax(geom),"
        " ST_XMax(geom), ST_Y(ST_Centroid(geom)), ST_X(ST_Centroid(geom))"
        " FROM buildings"
    ).fetchall()
    conn.execute(
        "CREATE TEMP TABLE building_ubid (building_id bigint, ubid text) ON COMMIT DROP"
    )
    with conn.cursor().copy("COPY building_ubid FROM STDIN") as copy:
        for building_id, *box in rows:
            copy.write_row((building_id, ubid.encode(*box)))
    conn.execute(
        "UPDATE buildings b SET ubid = u.ubid FROM building_ubid u"
        " WHERE u.building_id = b.building_id"
    )


def build(conn) -> None:
    with conn.transaction():
        fill_use_code_classes(conn, use_codes.load())
        fill_pilot_towns(conn, load_regions())
        for step in STEPS:
            if callable(step):
                step(conn)
            else:
                conn.execute((SQL / step).read_text())


def main() -> None:
    with connect(autocommit=True) as conn:
        build(conn)
        for table in (
            "parcels",
            "buildings",
            "sites",
            "lber_matches",
            "lber_unmatched",
        ):
            n = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            print(f"{table}: {n:,}")


if __name__ == "__main__":
    main()
