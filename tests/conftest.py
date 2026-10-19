import os
import uuid

import psycopg
import pytest

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
