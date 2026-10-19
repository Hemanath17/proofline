"""Regression test for a race the reviewer agent found while checking
Step 7's new code: `get_or_create_document_disposition`
(`db/repository.py`) did a plain check-then-insert with no compare-and-set
and no `IntegrityError` handling. Two concurrent *first-time*
`confirm_disposition` calls on the same never-before-disposed document
could both see no existing row and both try to insert one at the same
primary key (`document_id`) -- caught by the table's own primary-key
constraint at the database level, surfacing as an uncaught
`sqlalchemy.exc.IntegrityError` (a bare 500) rather than the 409
acceptance test I2 calls for. Unlike the sign-off race
(`test_sign_off_race.py`), `confirm_disposition` *does* have its own
`expected_revision`/compare-and-set (`DocumentDisposition.revision`), so
exactly one of 20 concurrent first-time confirmations should succeed and
every other one should come back a clean 409, never a 500.
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

PRIYA = "st-01"


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


def test_twenty_concurrent_first_confirmations_give_one_200_and_nineteen_409s(
    pg_client: TestClient,
) -> None:
    results: list[int] = []
    bodies: list[dict] = []
    lock = threading.Lock()
    concurrency = 20
    barrier = threading.Barrier(concurrency)

    def _confirm() -> None:
        barrier.wait()
        response = pg_client.post(
            "/api/documents/D09/confirm-disposition",
            json={"expected_revision": 1, "disposition": "used"},
            headers=_headers(PRIYA),
        )
        with lock:
            results.append(response.status_code)
            bodies.append(response.json())

    threads = [threading.Thread(target=_confirm) for _ in range(concurrency)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert all(status in (200, 409) for status in results), results
    assert results.count(200) == 1, results
    assert results.count(409) == concurrency - 1, results

    for status, body in zip(results, bodies, strict=True):
        if status == 409:
            assert "current_state" in body, body
            assert body["current_state"]["document_id"] == "D09"
