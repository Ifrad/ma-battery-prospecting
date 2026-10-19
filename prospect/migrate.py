"""Apply numbered SQL migrations from sql/migrations in order, once each.

Files are named NNNN_description.sql. Each runs in its own transaction
together with its row in schema_migrations, so a failed migration leaves
nothing half applied.
"""

import re
from pathlib import Path

from prospect.db import connect

MIGRATIONS = Path(__file__).resolve().parent.parent / "sql" / "migrations"
NAME = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


def pending(applied: set[str], directory: Path = MIGRATIONS) -> list[Path]:
    """Migration files not yet applied, in number order."""
    files = sorted(directory.glob("*.sql"))
    numbers = []
    for path in files:
        match = NAME.match(path.name)
        if not match:
            raise ValueError(f"bad migration name: {path.name}")
        numbers.append(match.group(1))
    if len(set(numbers)) != len(numbers):
        raise ValueError(f"duplicate migration numbers in {directory}")
    return [path for path in files if path.stem not in applied]


def migrate(conn, directory: Path = MIGRATIONS) -> list[str]:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " version text PRIMARY KEY,"
        " applied_at timestamptz NOT NULL DEFAULT now())"
    )
    conn.commit()
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    done = []
    for path in pending(applied, directory):
        with conn.transaction():
            conn.execute(path.read_text())
            conn.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)", (path.stem,)
            )
        done.append(path.stem)
    return done


def main() -> None:
    with connect() as conn:
        done = migrate(conn)
    print("\n".join(f"applied {name}" for name in done) or "up to date")


if __name__ == "__main__":
    main()
