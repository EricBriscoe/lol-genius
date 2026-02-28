from __future__ import annotations

import logging

import psycopg2
import psycopg2.extras

from .schema import SCHEMA_SQL, MIGRATION_SQL

log = logging.getLogger(__name__)

_schema_verified: set[str] = set()

_MIGRATION_CANARY = ("player_recent_stats", "avg_multikill_rate")


def _run_schema(conn, sql: str) -> None:
    cur = conn.cursor()
    for stmt in sql.split(";"):
        stmt = stmt.strip()
        if stmt:
            cur.execute(stmt)
    conn.commit()
    cur.close()


def _needs_migration(conn) -> bool:
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = %s AND column_name = %s",
        _MIGRATION_CANARY,
    )
    exists = cur.fetchone() is not None
    cur.close()
    return not exists


def _run_migration_safe(conn) -> None:
    cur = conn.cursor()
    cur.execute("SET lock_timeout = '5s'")
    cur.close()
    try:
        _run_schema(conn, MIGRATION_SQL)
    except psycopg2.errors.LockNotAvailable:
        conn.rollback()
        log.warning("Migration deferred because active queries have locked the tables")
    finally:
        cur = conn.cursor()
        cur.execute("SET lock_timeout = 0")
        cur.close()


def _ensure_schema(conn, dsn: str) -> None:
    cur = conn.cursor()
    cur.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
    )
    tables = {r["table_name"] for r in cur.fetchall()}
    cur.close()

    if "matches" not in tables or "model_runs" not in tables:
        log.info("Auto-initializing database")
        _run_schema(conn, SCHEMA_SQL)
    elif dsn not in _schema_verified and _needs_migration(conn):
        _run_migration_safe(conn)

    _schema_verified.add(dsn)


def get_connection(dsn: str):
    conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    _ensure_schema(conn, dsn)
    return conn


def get_connection_fast(dsn: str):
    conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    if dsn not in _schema_verified:
        _ensure_schema(conn, dsn)
    return conn


def init_db(dsn: str) -> None:
    conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    _run_schema(conn, SCHEMA_SQL)
    conn.close()
