from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from proofline.app import app
from proofline.db.connection import get_engine
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool


@pytest.fixture
def client() -> Iterator[TestClient]:
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_health_ok_when_the_database_is_reachable(client: TestClient) -> None:
    working_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app.dependency_overrides[get_engine] = lambda: working_engine

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_returns_503_when_the_database_is_unreachable(
    client: TestClient,
) -> None:
    broken_engine = create_engine("sqlite:////nonexistent/path/does-not-exist.db")
    app.dependency_overrides[get_engine] = lambda: broken_engine

    response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json() == {"detail": "database unreachable"}


def test_health_503_never_leaks_the_underlying_exception_text(
    client: TestClient,
) -> None:
    """The driver's own error message can carry a hostname, database name or
    file path -- none of that may reach the client of this unauthenticated
    endpoint."""
    broken_engine = create_engine("sqlite:////nonexistent/path/does-not-exist.db")
    app.dependency_overrides[get_engine] = lambda: broken_engine

    response = client.get("/api/health")

    assert "nonexistent" not in response.text
    assert "does-not-exist" not in response.text
    assert "sqlite" not in response.text.lower()
