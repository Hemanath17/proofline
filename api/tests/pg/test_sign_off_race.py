"""Regression test for a race `/deep-test` found while reviewing Step 7's
new code: `sign_offs.sign_off` computed `previous.version + 1` and inserted
a new `SignOff` row with no compare-and-set of its own -- two reviewers
racing to sign the same scope could both read the same `previous.version`
and both try to insert the same (scope, version), which the table's own
unique index catches at the database level. Before the fix, that surfaced
as an uncaught `sqlalchemy.exc.IntegrityError` -- a bare 500 (no handler
for it in `app.py`), where a clean 409 is what acceptance test I2's own
spirit calls for.

`sign_off` has no `expected_revision` of its own (unlike a case
transition), so several concurrent callers are allowed to each
successfully create a new, distinct version -- that's not a race, it's
20 independent appends, the same as 20 concurrent `add_review_note`
calls each creating a different note. The one thing that must never
happen is two of them landing on the *same* version number (a lost
update that would silently discard one signer's fingerprints) or a
request crashing instead of getting a clean answer -- those are what
this test actually asserts.
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


def test_twenty_concurrent_sign_offs_never_crash_or_duplicate_a_version(
    pg_client: TestClient,
) -> None:
    results: list[int] = []
    bodies: list[dict] = []
    lock = threading.Lock()
    concurrency = 20
    barrier = threading.Barrier(concurrency)

    def _sign_off() -> None:
        barrier.wait()
        response = pg_client.post(
            "/api/areas/pass_throughs/sign-off",
            json={"version": "v1"},
            headers=_headers(DANIEL),
        )
        with lock:
            results.append(response.status_code)
            bodies.append(response.json())

    threads = [threading.Thread(target=_sign_off) for _ in range(concurrency)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # No bare 500s, regardless of how many of the 20 happened to overlap
    # enough to actually collide.
    assert all(status in (200, 409) for status in results), results
    assert results.count(200) >= 1, results

    succeeded_versions = [
        body["version"]
        for status, body in zip(results, bodies, strict=True)
        if status == 200
    ]
    # The one invariant that must hold no matter how the race falls:
    # never two successes at the same version (a lost update).
    assert len(succeeded_versions) == len(set(succeeded_versions)), succeeded_versions

    for status, body in zip(results, bodies, strict=True):
        if status == 409:
            assert "current_state" in body, body
