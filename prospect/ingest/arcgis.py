"""Load an ArcGIS feature layer into a raw_* table, page by page.

Each load covers one scope (a where clause such as "TOWN_ID=44") and gets a
row in ingest_runs. Pages are requested in object id order and committed one
at a time, so an interrupted load resumes after the last id it stored. Rows
are upserted on object id, and rows of the scope that the source no longer
serves are deleted at the end, so reruns never duplicate or leave stale rows.
"""

import json
from collections.abc import Iterator

from psycopg import sql
from psycopg.types.json import Jsonb

from prospect.ingest.client import Client

PAGE_SIZE = 2000


def _query(client: Client, url: str, params: dict) -> dict:
    reply = client.get(f"{url}/query", params=params).json()
    if "error" in reply:
        raise RuntimeError(f"{url}: {reply['error']}")
    return reply


def object_id_field(client: Client, url: str) -> str:
    return client.get(url, params={"f": "json"}).json()["objectIdField"]


def count(client: Client, url: str, where: str) -> int:
    reply = _query(
        client, url, {"where": where, "returnCountOnly": "true", "f": "json"}
    )
    return reply["count"]


def fetch_pages(
    client: Client, url: str, where: str, oid: str, after: int = 0
) -> Iterator[list[dict]]:
    """Yield GeoJSON feature pages with object id above `after`, in id order."""
    while True:
        page = _query(
            client,
            url,
            {
                "where": f"({where}) AND {oid} > {after}",
                "outFields": "*",
                "orderByFields": oid,
                "resultRecordCount": PAGE_SIZE,
                "outSR": 4326,
                "geometryPrecision": 6,
                "f": "geojson",
            },
        )
        features = page["features"]
        if not features:
            return
        yield features
        after = features[-1]["id"]


def _start_run(conn, source: str, url: str, scope: str) -> tuple[int, bool]:
    """Reuse the newest unfinished run for this scope, or start a new one."""
    row = conn.execute(
        "SELECT id FROM ingest_runs"
        " WHERE source = %s AND scope = %s AND status IN ('running', 'failed')"
        " AND id > coalesce((SELECT max(id) FROM ingest_runs"
        "   WHERE source = %s AND scope = %s AND status = 'succeeded'), 0)"
        " ORDER BY id DESC LIMIT 1",
        (source, scope, source, scope),
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE ingest_runs SET status = 'running', error = NULL WHERE id = %s",
            row,
        )
        return row[0], True
    row = conn.execute(
        "INSERT INTO ingest_runs (source, url, scope) VALUES (%s, %s, %s) RETURNING id",
        (source, url, scope),
    ).fetchone()
    return row[0], False


def load(conn, client: Client, source: str, url: str, table: str, scope: str) -> dict:
    """Load one scope of a layer into `table`. `conn` must be in autocommit mode."""
    run_id, resumed = _start_run(conn, source, url, scope)
    t = sql.Identifier(table)
    try:
        oid = object_id_field(client, url)
        source_rows = count(client, url, scope)
        after = 0
        if resumed:
            after = conn.execute(
                sql.SQL(
                    "SELECT coalesce(max(objectid), 0) FROM {} WHERE run_id = %s"
                ).format(t),
                (run_id,),
            ).fetchone()[0]
        upsert = sql.SQL(
            "INSERT INTO {} (objectid, scope, run_id, attrs, geom)"
            " VALUES (%s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))"
            " ON CONFLICT (objectid) DO UPDATE SET scope = EXCLUDED.scope,"
            " run_id = EXCLUDED.run_id, attrs = EXCLUDED.attrs, geom = EXCLUDED.geom"
        ).format(t)
        for features in fetch_pages(client, url, scope, oid, after):
            rows = [
                (
                    f["id"],
                    scope,
                    run_id,
                    Jsonb(f["properties"]),
                    json.dumps(f["geometry"]) if f.get("geometry") else None,
                )
                for f in features
            ]
            with conn.transaction(), conn.cursor() as cur:
                cur.executemany(upsert, rows)
        with conn.transaction():
            conn.execute(
                sql.SQL("DELETE FROM {} WHERE scope = %s AND run_id <> %s").format(t),
                (scope, run_id),
            )
            rows, digest = conn.execute(
                sql.SQL(
                    "SELECT count(*), encode(sha256(convert_to(coalesce(string_agg("
                    "objectid::text || ' ' || attrs::text || ' ' ||"
                    " coalesce(md5(ST_AsBinary(geom)), ''),"
                    " E'\\n' ORDER BY objectid), ''), 'UTF8')), 'hex')"
                    " FROM {} WHERE run_id = %s"
                ).format(t),
                (run_id,),
            ).fetchone()
            conn.execute(
                "UPDATE ingest_runs SET status = 'succeeded', finished_at = now(),"
                " rows = %s, source_rows = %s, sha256 = %s WHERE id = %s",
                (rows, source_rows, digest, run_id),
            )
    except Exception as exc:
        conn.execute(
            "UPDATE ingest_runs SET status = 'failed', finished_at = now(),"
            " error = %s WHERE id = %s",
            (f"{type(exc).__name__}: {exc}", run_id),
        )
        raise
    return {
        "run_id": run_id,
        "rows": rows,
        "source_rows": source_rows,
        "resumed": resumed,
    }
