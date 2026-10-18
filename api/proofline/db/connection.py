from __future__ import annotations

import os
from collections.abc import Iterator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.orm import Session

load_dotenv(".env.local")

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
        _engine = create_engine(get_database_url())
    return _engine


def get_session() -> Iterator[Session]:
    session = Session(get_engine())
    try:
        yield session
    finally:
        session.close()
