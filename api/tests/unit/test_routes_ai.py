"""`POST /api/cases/{case_id}/investigate` and `.../suggestions/{id}/review`.

`investigate` itself needs a real GROQ_API_KEY to run the model, so that
path is covered separately under `api/eval/` (marked `eval`, skipped
without the key). What's tested here, without any model call and without
GROQ_API_KEY, is everything deterministic: the config-error path, the
staff-only guard on both routes, and the whole review/accept/reject path
against a suggestion seeded directly through `proofline.ai.events`
(exactly the shape a real investigation would have written).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from proofline.ai import events as ai_events
from sqlalchemy.orm import Session

PRIYA = "st-01"  # preparer
DANIEL = "st-02"  # reviewer
CLIENT = "cu-01"
AI_ASSISTANT = "ai-assistant"


def _headers(actor_id: str) -> dict[str, str]:
    return {"X-Proofline-Actor": actor_id}


def _open_investigating_case(client: TestClient) -> tuple[str, int]:
    synced = client.post("/api/cases/sync", headers=_headers(DANIEL))
    case = next(c for c in synced.json()["cases"] if c["status"] == "open")
    picked_up = client.post(
        f"/api/cases/{case['case_id']}/pick-up",
        json={"expected_revision": case["revision"]},
        headers=_headers(PRIYA),
    )
    body = picked_up.json()
    return body["case_id"], body["revision"]


@pytest.fixture(autouse=True)
def _no_groq_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("AI_INVESTIGATOR_ENABLED", raising=False)


def test_investigate_is_disabled_by_default_even_with_a_key(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AI_INVESTIGATOR_ENABLED defaults to false regardless of
    GROQ_API_KEY -- it only flips once `api/eval`'s golden-set run
    actually clears the bar (docs/DECISIONS.md)."""
    monkeypatch.setenv("GROQ_API_KEY", "would-be-a-real-key")
    case_id, _ = _open_investigating_case(client)
    response = client.post(f"/api/cases/{case_id}/investigate", headers=_headers(PRIYA))
    assert response.status_code == 503
    assert "not enabled" in response.json()["detail"]


def test_investigate_without_groq_api_key_returns_a_clear_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AI_INVESTIGATOR_ENABLED", "true")
    case_id, _ = _open_investigating_case(client)
    response = client.post(f"/api/cases/{case_id}/investigate", headers=_headers(PRIYA))
    assert response.status_code == 503
    assert "GROQ_API_KEY" in response.json()["detail"]


def test_investigate_is_blocked_for_the_client(client: TestClient) -> None:
    case_id, _ = _open_investigating_case(client)
    response = client.post(
        f"/api/cases/{case_id}/investigate", headers=_headers(CLIENT)
    )
    assert response.status_code == 403


def test_investigate_missing_case_is_404(client: TestClient) -> None:
    response = client.post(
        "/api/cases/does-not-exist/investigate", headers=_headers(PRIYA)
    )
    assert response.status_code == 404


def _seed_suggestion(db_session: Session, case_id: str) -> str:
    event = ai_events.record_suggestion(
        db_session,
        case_id=case_id,
        model_name="llama-3.3-70b-versatile",
        prompt_version=1,
        schema_version=1,
        tool_calls=[{"name": "open_case", "args": {"case_id": case_id}}],
        validation_ok=True,
        validation_reasons=(),
        suggestion={
            "summary": "Looks legitimate given the evidence on file.",
            "cited_claim_ids": [],
            "cited_document_ids": ["D01"],
            "numbers_cited": [],
            "proposed_resolution_type": "mark_legitimate",
            "proposed_fields": {"reason": "expected variance"},
            "confidence": "supported",
        },
    )
    db_session.commit()
    return str(event.id)


def test_review_reject_writes_a_reviewed_event_and_no_proposal(
    client: TestClient, db_session: Session
) -> None:
    case_id, _ = _open_investigating_case(client)
    suggestion_id = _seed_suggestion(db_session, case_id)

    response = client.post(
        f"/api/cases/{case_id}/suggestions/{suggestion_id}/review",
        json={"decision": "reject"},
        headers=_headers(DANIEL),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["proposal_id"] is None
    assert body["case"]["status"] == "investigating"  # unchanged


def test_review_accept_calls_submit_proposal_for_real(
    client: TestClient, db_session: Session
) -> None:
    case_id, revision = _open_investigating_case(client)
    suggestion_id = _seed_suggestion(db_session, case_id)

    # submit_proposal is preparer-only, same role rule as a manually-typed
    # proposal -- accepting an AI suggestion goes through that exact same
    # action, not a second path into the case pipeline.
    response = client.post(
        f"/api/cases/{case_id}/suggestions/{suggestion_id}/review",
        json={"decision": "accept", "expected_revision": revision},
        headers=_headers(PRIYA),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["proposal_id"] is not None
    assert body["case"]["status"] == "in_review"

    # The ordinary case-detail view shows it labeled, separate from the
    # real proposal it produced.
    detail = client.get(f"/api/cases/{case_id}", headers=_headers(DANIEL)).json()
    assert detail["ai_suggestions"][0]["label"] == "AI-suggested"
    assert detail["ai_suggestions"][0]["reviews"][0]["decision"] == "accept"
    assert len(detail["proposals"]) == 1
    assert detail["proposals"][0]["resolution_type"] == "mark_legitimate"


def test_review_accept_without_expected_revision_is_422(
    client: TestClient, db_session: Session
) -> None:
    case_id, _ = _open_investigating_case(client)
    suggestion_id = _seed_suggestion(db_session, case_id)
    response = client.post(
        f"/api/cases/{case_id}/suggestions/{suggestion_id}/review",
        json={"decision": "accept"},
        headers=_headers(DANIEL),
    )
    assert response.status_code == 422


def test_review_is_blocked_for_the_client_and_the_ai_assistant(
    client: TestClient, db_session: Session
) -> None:
    case_id, _ = _open_investigating_case(client)
    suggestion_id = _seed_suggestion(db_session, case_id)
    for actor_id in (CLIENT, AI_ASSISTANT):
        response = client.post(
            f"/api/cases/{case_id}/suggestions/{suggestion_id}/review",
            json={"decision": "reject"},
            headers=_headers(actor_id),
        )
        assert response.status_code == 403, actor_id


def test_review_unknown_suggestion_is_404(client: TestClient) -> None:
    case_id, _ = _open_investigating_case(client)
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = client.post(
        f"/api/cases/{case_id}/suggestions/{fake_id}/review",
        json={"decision": "reject"},
        headers=_headers(DANIEL),
    )
    assert response.status_code == 404
