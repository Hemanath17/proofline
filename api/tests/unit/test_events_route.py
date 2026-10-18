from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from proofline.app import app
from proofline.db.connection import get_session
from proofline.db.models import Base


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def override_get_session() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_write_then_read_event(client: TestClient) -> None:
    create_response = client.post(
        "/api/events",
        json={"event_type": "test_event", "payload": {"foo": "bar"}},
    )
    assert create_response.status_code == 200
    event_id = create_response.json()["id"]

    read_response = client.get(f"/api/events/{event_id}")
    assert read_response.status_code == 200
    body = read_response.json()
    assert body["event_type"] == "test_event"
    assert body["payload"] == {"foo": "bar"}


def test_read_missing_event_returns_404(client: TestClient) -> None:
    import uuid

    response = client.get(f"/api/events/{uuid.uuid4()}")
    assert response.status_code == 404
