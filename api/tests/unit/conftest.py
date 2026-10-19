"""Shared fixtures for route-level tests: an in-memory SQLite session and a
TestClient wired to it instead of the real (Postgres) engine, replicating
`proofline.db.connection.get_session`'s commit-on-success /
rollback-on-exception behavior so route tests see the same semantics as a
real request.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from proofline.app import app
from proofline.db.connection import get_session
from proofline.db.models import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


@pytest.fixture
def db_session() -> Iterator[Session]:
    # TestClient dispatches each request on its own worker thread, and a
    # plain sqlite "/:memory:" engine hands out a brand new, separate
    # (empty) in-memory database per thread/connection -- StaticPool keeps
    # every checkout on the one connection the fixture created, so the
    # tables created below still exist by the time a request handles it.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    def _get_session_override() -> Iterator[Session]:
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    app.dependency_overrides[get_session] = _get_session_override
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
