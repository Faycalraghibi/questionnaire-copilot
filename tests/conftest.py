import os

import psycopg
import pytest

from qc.db import connect


@pytest.fixture(scope="session")
def db_conn():
    """Connection to the Docker database. Skips when it is not running, unless
    QC_REQUIRE_DB=1 (set in CI) turns that into a failure."""
    try:
        conn = connect()
    except psycopg.OperationalError as exc:
        if os.environ.get("QC_REQUIRE_DB") == "1":
            raise
        pytest.skip(f"database not reachable, run `make up` first ({exc.__class__.__name__})")
    yield conn
    conn.close()
