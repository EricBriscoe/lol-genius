import os
import subprocess

import psycopg2
import pytest

from lol_genius.db.connection import dbmate_url
from lol_genius.db.queries import MatchDB

_TEST_DB_BASE = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://lol_genius:lol_genius_dev@localhost:5432/postgres",
)
_TEST_DB_NAME = "lol_genius_test"
_TEST_DSN = _TEST_DB_BASE.rsplit("/", 1)[0] + f"/{_TEST_DB_NAME}"


def _create_test_db():
    conn = psycopg2.connect(_TEST_DB_BASE)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(f"DROP DATABASE IF EXISTS {_TEST_DB_NAME}")
    cur.execute(f"CREATE DATABASE {_TEST_DB_NAME}")
    cur.close()
    conn.close()


def _drop_test_db():
    conn = psycopg2.connect(_TEST_DB_BASE)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(f"""
        SELECT pg_terminate_backend(pid) FROM pg_stat_activity
        WHERE datname = '{_TEST_DB_NAME}' AND pid <> pg_backend_pid()
    """)
    cur.execute(f"DROP DATABASE IF EXISTS {_TEST_DB_NAME}")
    cur.close()
    conn.close()


@pytest.fixture(scope="session", autouse=True)
def _setup_test_db():
    _create_test_db()
    subprocess.run(
        ["dbmate", "up"],
        env={**os.environ, "DATABASE_URL": dbmate_url(_TEST_DSN)},
        check=True,
    )
    yield
    _drop_test_db()


@pytest.fixture
def test_dsn():
    return _TEST_DSN


@pytest.fixture
def db(test_dsn):
    conn = psycopg2.connect(test_dsn)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("""
        DO $$ DECLARE r RECORD;
        BEGIN
            FOR r IN (
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public' AND tablename <> 'schema_migrations'
            ) LOOP
                EXECUTE 'TRUNCATE TABLE ' || quote_ident(r.tablename) || ' CASCADE';
            END LOOP;
        END $$
    """)
    cur.close()
    conn.close()

    d = MatchDB(test_dsn)
    yield d
    d.close()
