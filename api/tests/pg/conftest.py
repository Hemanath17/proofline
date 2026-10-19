"""Shared setup for Postgres-only tests (marker `pg`): skipped when
`TEST_DATABASE_URL` isn't set, refusing to run at all if it equals
`DATABASE_URL` (the demo database is never touched by a test run), and
resetting the schema and applying every real migration at the start of
each test that asks for `pg_engine`.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine, make_url

_API_DIR = Path(__file__).resolve().parents[2]
_ALEMBIC_INI = _API_DIR / "alembic.ini"


def _normalized_url(raw: str) -> URL:
    url = make_url(raw).set(drivername="postgresql+psycopg")
    query = dict(url.query)
    query.setdefault("sslmode", "require")
    return url.set(query=query)


def _test_database_url() -> str:
    test_url = os.environ.get("TEST_DATABASE_URL")
    if not test_url:
        pytest.skip("TEST_DATABASE_URL not set -- skipping Postgres-only tests")
    demo_url = os.environ.get("DATABASE_URL")
    if demo_url and test_url == demo_url:
        pytest.fail(
            "TEST_DATABASE_URL must not equal DATABASE_URL -- refusing to run "
            "Postgres-only tests against the demo database"
        )
    return test_url


def _reset_schema(url: URL) -> None:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            connection.execute(text("DROP SCHEMA public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
            connection.commit()
    finally:
        engine.dispose()


def _upgrade_head(raw_test_url: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(_ALEMBIC_INI), "upgrade", "head"],
        cwd=_API_DIR,
        env={**os.environ, "DATABASE_URL": raw_test_url},
        check=True,
    )


@pytest.fixture
def pg_engine() -> Iterator[Engine]:
    raw_test_url = _test_database_url()
    url = _normalized_url(raw_test_url)
    _reset_schema(url)
    _upgrade_head(raw_test_url)

    engine = create_engine(url)
    try:
        yield engine
    finally:
        engine.dispose()
