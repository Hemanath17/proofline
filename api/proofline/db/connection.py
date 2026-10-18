from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.orm import Session

_REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_REPO_ROOT / ".env.local")

_engine: Engine | None = None


def get_database_url() -> URL:
    """The real connection URL as a SQLAlchemy URL object, never a plain string.

    Keeping it as a URL object means str()/repr() on it (logs, tracebacks,
    accidental prints) mask the password by default. Only create_engine()
    and similar APIs that accept a URL object directly should receive this.
    """
    raw = os.environ["DATABASE_URL"]
    url = make_url(raw).set(drivername="postgresql+psycopg")
    query = dict(url.query)
    query.setdefault("sslmode", "require")
    return url.set(query=query)


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(get_database_url(), pool_pre_ping=True)
    return _engine


def get_session() -> Iterator[Session]:
    session = Session(get_engine())
    try:
        yield session
    finally:
        session.close()


def check_connection(engine: Engine) -> None:
    """Raises if the database can't be reached. This is the one place
    outside this module that's allowed to know the database is reachable
    (routes/health.py) -- it calls this instead of touching SQL itself, so
    `proofline/db/` stays the only code that does."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
