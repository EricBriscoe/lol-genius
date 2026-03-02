from __future__ import annotations

import psycopg2
import psycopg2.extras
from psycopg2 import pool as pg_pool


def get_connection(dsn: str):
    return psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)


def create_pool(dsn: str, minconn: int = 1, maxconn: int = 5) -> pg_pool.ThreadedConnectionPool:
    return pg_pool.ThreadedConnectionPool(
        minconn, maxconn, dsn, cursor_factory=psycopg2.extras.RealDictCursor
    )


def dbmate_url(dsn: str) -> str:
    if "sslmode" in dsn:
        return dsn
    return dsn + ("&" if "?" in dsn else "?") + "sslmode=disable"
