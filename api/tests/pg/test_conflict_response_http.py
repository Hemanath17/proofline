"""Regression test for the bug a real-Postgres check found: `_conflict_response`
(proofline/app.py) used to call `.to_dict()` on the live ORM row carried by
`StaleRevision`/`ActionConflict`, after the request's session had already
closed -- raising `DetachedInstanceError` and turning every 409 into a bare
500. 20 concurrent HTTP responses at the same revision used to come back
1x200 and 19x500, where 19x409 (with `current_state` in the body) is what
acceptance test I2 requires. `StaleRevision`/`ActionConflict` now carry a
plain dict, captured by the raise site while its own session was still
open, so this only reproduces if that regresses.

Runs over real HTTP (`TestClient`, in-process, no socket) against the
throwaway Postgres database, through the same `get_session`-shaped
dependency override `closing_client` uses on SQLite -- herewired to
`pg_engine` so the detachment is the real Postgres one, not SQLite's.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from proofline.app import app
from proofline.db.connection import get_session
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

pytestmark = pytest.mark.pg

DANIEL = "st-02"
PRIYA = "st-01"
MARCUS = "st-04"


def _headers(actor_id: str) -> dict[str, str]:
    return {"X-Proofline-Actor": actor_id}


@pytest.fixture
def pg_client(pg_engine: Engine) -> Iterator[TestClient]:
    def _get_session_override() -> Iterator[Session]:
        session = Session(pg_engine)
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_session] = _get_session_override
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def test_twenty_concurrent_responses_give_one_200_and_nineteen_409s(
    pg_client: TestClient,
) -> None:
    note = pg_client.post(
        "/api/review-notes",
        json={"about_type": "document", "about_id": "D30", "body": "check this"},
        headers=_headers(DANIEL),
    ).json()

    results: list[int] = []
    bodies: list[dict] = []
    lock = threading.Lock()
    concurrency = 20
    barrier = threading.Barrier(concurrency)

    def _respond() -> None:
        barrier.wait()
        response = pg_client.post(
            f"/api/review-notes/{note['id']}/respond",
            json={"expected_revision": 1, "body": "racing"},
            headers=_headers(PRIYA),
        )
        with lock:
            results.append(response.status_code)
            bodies.append(response.json())

    threads = [threading.Thread(target=_respond) for _ in range(concurrency)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert results.count(200) == 1, results
    assert results.count(409) == concurrency - 1, results
    assert all(status in (200, 409) for status in results), results

    for status, body in zip(results, bodies, strict=True):
        if status == 409:
            assert "current_state" in body, body
            assert body["current_state"]["revision"] == 2


def test_responding_to_a_resolved_note_returns_409_against_postgres(
    pg_client: TestClient,
) -> None:
    note = pg_client.post(
        "/api/review-notes",
        json={"about_type": "document", "about_id": "D31", "body": "check this"},
        headers=_headers(DANIEL),
    ).json()
    pg_client.post(
        f"/api/review-notes/{note['id']}/resolve",
        json={"expected_revision": 1, "resolution": "fixed"},
        headers=_headers(DANIEL),
    )

    response = pg_client.post(
        f"/api/review-notes/{note['id']}/respond",
        json={"expected_revision": 2, "body": "too late"},
        headers=_headers(MARCUS),
    )

    assert response.status_code == 409
    body = response.json()
    assert body["detail"] == "cannot respond to a resolved note"
    assert body["current_state"]["status"] == "resolved"
