"""W4 (docs/ACCEPTANCE.md): the client sees a labelled summary, answers
their questions, approves and signs, and the signature is tied to that
exact package -- end to end against the real packet, through the actual
client-workspace routes (not a direct `perform()` call), since W4 is
specifically about what Ngozi can reach and see through the API.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from proofline.app import app
from proofline.db.connection import get_session
from proofline.db.models import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

PRIYA = "st-01"  # preparer
NGOZI = "cu-01"  # client (taxpayer)


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Same shape as `api/tests/unit/conftest.py`'s `client` fixture --
    duplicated here (not shared) since this is the only acceptance test
    that needs an HTTP-level `TestClient` rather than a direct `perform()`
    call, unlike A1-A3."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db_session:

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


def _headers(actor_id: str) -> dict[str, str]:
    return {"X-Proofline-Actor": actor_id}


def test_w4_client_workspace_walkthrough(client: TestClient) -> None:
    # 1. Ngozi reads her labelled summary.
    summary = client.get("/api/client/summary", headers=_headers(NGOZI))
    assert summary.status_code == 200
    summary_body = summary.json()
    assert summary_body["federal"]["label"].startswith("Engine")
    assert "balance_due" in summary_body["federal"]

    # 2. A case with a client question exists, and Priya asks it.
    synced = client.post("/api/cases/sync", headers=_headers(PRIYA))
    cases = synced.json()["cases"]
    assert cases, "the real packet should produce at least one case"
    case_id = next(
        c["case_id"] for c in cases if c["status"] in ("open", "investigating")
    )
    picked_up = client.post(
        f"/api/cases/{case_id}/pick-up",
        json={"expected_revision": 1},
        headers=_headers(PRIYA),
    )
    assert picked_up.status_code == 200
    asked = client.post(
        f"/api/cases/{case_id}/ask-client",
        json={
            "expected_revision": picked_up.json()["revision"],
            "question": "Can you confirm the cost basis on this lot?",
        },
        headers=_headers(PRIYA),
    )
    assert asked.status_code == 200

    # Before answering, Ngozi sees the open question with no answer yet.
    before = client.get("/api/client/questions", headers=_headers(NGOZI)).json()
    thread_before = next(t for t in before["threads"] if t["case_id"] == case_id)
    assert thread_before["answer"] is None

    # 3. Ngozi answers her own question.
    answered = client.post(
        f"/api/cases/{case_id}/client-answered",
        json={"expected_revision": asked.json()["revision"], "evidence_ref": "msg-01"},
        headers=_headers(NGOZI),
    )
    assert answered.status_code == 200

    after = client.get("/api/client/questions", headers=_headers(NGOZI)).json()
    thread_after = next(t for t in after["threads"] if t["case_id"] == case_id)
    assert thread_after["answer"] is not None

    # 4. Ngozi sees the package she's about to sign, with both
    # fingerprints -- "signing authorizes this exact package" (W4).
    package = client.get("/api/client/package", headers=_headers(NGOZI))
    assert package.status_code == 200
    package_body = package.json()
    assert package_body["reference"]
    assert package_body["amounts_fingerprint"]
    assert package_body["identity_fingerprint"]

    # 5. Ngozi approves and signs -- the existing authorize_filing action,
    # not a second signing mechanism.
    authorized = client.post(
        "/api/filing/authorize",
        json={"pins": {"taxpayer": "41207", "spouse": "88310"}},
        headers=_headers(NGOZI),
    )
    assert authorized.status_code == 200
    assert authorized.json()["package_reference"] == package_body["reference"]

    # The client workspace is the only surface Ngozi reaches -- the full
    # staff surface stays blocked, even after signing.
    blocked = client.get("/api/areas/investments", headers=_headers(NGOZI))
    assert blocked.status_code == 403
