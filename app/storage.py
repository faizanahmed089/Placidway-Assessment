"""Small SQLite store for two nice-to-have features:

  * leads              - name + email of visitors who ask for a quote
  * unanswered         - questions the bot could not answer, so the content
                         team can see which topics the pages are missing

SQLite needs no server and no account. A new connection is opened per call,
which is the simple, thread-safe way to use it from a web server.
"""

import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from app import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    name       TEXT NOT NULL,
    email      TEXT NOT NULL,
    question   TEXT
);
CREATE TABLE IF NOT EXISTS unanswered (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at   TEXT NOT NULL,
    message      TEXT NOT NULL,   -- what the visitor typed
    search_query TEXT,            -- standalone English version used for retrieval
    reason       TEXT NOT NULL,   -- not_found | guardrail_blocked | llm_error
    best_score   REAL             -- top similarity: low = topic missing from the pages
);
"""


def _connect() -> sqlite3.Connection:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(config.DB_FILE)
    connection.row_factory = sqlite3.Row  # rows behave like dicts
    return connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_db() -> None:
    """Create the tables if they do not exist yet (called once at startup)."""
    with closing(_connect()) as connection, connection:
        connection.executescript(_SCHEMA)


def save_lead(name: str, email: str, question: str) -> None:
    # "?" placeholders let SQLite escape the values -> no SQL injection.
    with closing(_connect()) as connection, connection:
        connection.execute(
            "INSERT INTO leads (created_at, name, email, question) VALUES (?, ?, ?, ?)",
            (_now(), name, email, question),
        )


def log_unanswered(message: str, search_query: str, reason: str, best_score: float) -> None:
    with closing(_connect()) as connection, connection:
        connection.execute(
            "INSERT INTO unanswered (created_at, message, search_query, reason, best_score) "
            "VALUES (?, ?, ?, ?, ?)",
            (_now(), message, search_query, reason, round(best_score, 3)),
        )


def list_rows(table: str, limit: int = 200) -> list[dict]:
    """Newest rows of a table, for the admin endpoints."""
    if table not in ("leads", "unanswered"):  # table names cannot be parameterised
        raise ValueError("unknown table")
    with closing(_connect()) as connection:
        rows = connection.execute(
            f"SELECT * FROM {table} ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]
