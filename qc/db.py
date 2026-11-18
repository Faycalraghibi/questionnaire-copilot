"""Database connection and migrations."""

from pathlib import Path

import psycopg

from qc.config import get_settings

SQL_DIR = Path(__file__).parent / "sql"

# Tables in dependency order (children first) for a full reset.
TABLES = [
    "run_steps",
    "reviews",
    "drafts",
    "questions",
    "questionnaires",
    "answer_library",
    "chunks",
    "policy_versions",
    "policies",
]


def connect(url: str | None = None) -> psycopg.Connection:
    return psycopg.connect(url or get_settings().database_url)


def migrate(conn: psycopg.Connection) -> list[str]:
    """Apply every qc/sql/NNN_*.sql file not applied yet. Returns the names applied."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " name TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
    )
    done = {r[0] for r in conn.execute("SELECT name FROM schema_migrations")}
    applied = []
    for path in sorted(SQL_DIR.glob("*.sql")):
        if path.name in done:
            continue
        conn.execute(path.read_text(encoding="utf-8"))
        conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
        applied.append(path.name)
    conn.commit()
    return applied


def reset(conn: psycopg.Connection) -> None:
    """Empty every product table. Keeps the schema."""
    conn.execute(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE")
    conn.commit()
