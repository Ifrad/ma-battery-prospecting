import json
import os
import uuid

import psycopg
import pytest
from psycopg.types.json import Jsonb

from prospect.db import connect
from prospect.migrate import migrate


@pytest.fixture
def db():
    """Autocommit connection to a fresh, migrated schema, dropped afterwards.

    Skips when no database is reachable, unless PROSPECT_REQUIRE_DB is set
    (as in CI), where a missing database is a failure.
    """
    try:
        conn = connect(autocommit=True)
    except psycopg.OperationalError:
        if os.environ.get("PROSPECT_REQUIRE_DB"):
            raise
        pytest.skip("no database; run make db-up")
    schema = f"test_{uuid.uuid4().hex[:12]}"
    conn.execute(f"CREATE SCHEMA {schema}")
    conn.execute(f"SET search_path TO {schema}, public")
    migrate(conn)
    yield conn
    conn.execute(f"DROP SCHEMA {schema} CASCADE")
    conn.close()


WORCESTER = 348


def box(x, y, size=0.001):
    """A square polygon as GeoJSON, lower left corner at (x, y) degrees."""
    x0, y0 = -71.8 + x, 42.26 + y
    ring = [
        [x0, y0],
        [x0 + size, y0],
        [x0 + size, y0 + size],
        [x0, y0 + size],
        [x0, y0],
    ]
    return json.dumps({"type": "Polygon", "coordinates": [ring]})


@pytest.fixture
def raw(db):
    run_id = db.execute(
        "INSERT INTO ingest_runs (source, url) VALUES ('test', 'test') RETURNING id"
    ).fetchone()[0]
    ids = iter(range(1, 1000))

    def parcel(loc_id, x, y, town=WORCESTER, **attrs):
        attrs = {"LOC_ID": loc_id, "TOWN_ID": town, **attrs}
        db.execute(
            "INSERT INTO raw_parcels (objectid, scope, run_id, attrs, geom)"
            " VALUES (%s, 'test', %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))",
            (next(ids), run_id, Jsonb(attrs), box(x, y)),
        )

    def footprint(x, y, sqft):
        attrs = {"STRUCT_ID": f"s{x}_{y}", "TOWN_ID": WORCESTER, "AREA_SQ_FT": sqft}
        db.execute(
            "INSERT INTO raw_footprints (objectid, scope, run_id, attrs, geom)"
            " VALUES (%s, 'test', %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))",
            (next(ids), run_id, Jsonb(attrs), box(x, y, 0.0002)),
        )

    return parcel, footprint
