"""Build the parcel, building and site tables from the raw tables.

Usage: python -m prospect.sites.build

Each run rebuilds everything in one transaction from sql/sites/*.sql, in
file name order, so it can be rerun at any time.
"""

from pathlib import Path

from prospect import use_codes
from prospect.db import connect

STEPS = Path(__file__).resolve().parents[2] / "sql" / "sites"


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


def build(conn) -> None:
    with conn.transaction():
        fill_use_code_classes(conn, use_codes.load())
        for step in sorted(STEPS.glob("*.sql")):
            conn.execute(step.read_text())


def main() -> None:
    with connect(autocommit=True) as conn:
        build(conn)
        for table in ("parcels", "buildings"):
            n = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            print(f"{table}: {n:,}")


if __name__ == "__main__":
    main()
