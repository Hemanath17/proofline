"""`proofline/ai/tools.py`: each tool is a thin wrapper over the exact
function the matching route already uses -- these tests drive them
directly (as the investigator would, via `ctx.deps`), not over HTTP, since
there is no model call involved. No GROQ_API_KEY needed; not marked
`eval`.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from proofline.ai import tools as ai_tools
from proofline.security.actors import AI_ASSISTANT_ID, Actor
from sqlalchemy.orm import Session

AI_ACTOR = Actor(
    id=AI_ASSISTANT_ID, name="AI assistant", role="ai_assistant", clearance=False
)


def _headers(actor_id: str) -> dict[str, str]:
    return {"X-Proofline-Actor": actor_id}


def test_trace_claim_on_a_line_key(client: TestClient, db_session: Session) -> None:
    result = ai_tools.trace_claim(AI_ACTOR, db_session, "F1040.1a")
    assert result["line_key"] == "F1040.1a"
    assert "inputs" in result and "used_by" in result


def test_trace_claim_on_a_document_id(client: TestClient, db_session: Session) -> None:
    result = ai_tools.trace_claim(AI_ACTOR, db_session, "D01")
    assert result["document_id"] == "D01"


def test_trace_claim_on_an_unresolvable_claim_raises(
    client: TestClient, db_session: Session
) -> None:
    with pytest.raises(ValueError, match="not a traceable claim"):
        ai_tools.trace_claim(AI_ACTOR, db_session, "no-such-claim-at-all")


def test_open_case_returns_the_case_and_is_masked(
    client: TestClient, db_session: Session
) -> None:
    synced = client.post("/api/cases/sync", headers=_headers("st-02"))
    case_id = synced.json()["cases"][0]["case_id"]

    result = ai_tools.open_case(AI_ACTOR, db_session, case_id)
    assert result["case_id"] == case_id
    assert "proposals" in result and "decisions" in result


def test_read_evidence_by_document_id_is_masked_like_an_uncleared_actor(
    client: TestClient, db_session: Session
) -> None:
    masked = ai_tools.read_evidence(AI_ACTOR, db_session, document_id="D01")
    cleared = client.get("/api/documents/D01", headers=_headers("st-02")).json()
    assert masked["id"] == "D01"
    assert "page_content" in masked
    # An uncleared read never gets more than an uncleared staff member does.
    assert masked.keys() <= {*cleared.keys(), "page_content"}


def test_read_evidence_needs_a_document_or_claim_id(
    client: TestClient, db_session: Session
) -> None:
    with pytest.raises(ValueError, match="needs either"):
        ai_tools.read_evidence(AI_ACTOR, db_session)


def test_find_related_documents_exact_id(
    client: TestClient, db_session: Session
) -> None:
    result = ai_tools.find_related_documents(AI_ACTOR, db_session, "D01")
    assert any(r["id"] == "D01" for r in result["results"])


def test_find_related_documents_full_text(
    client: TestClient, db_session: Session
) -> None:
    result = ai_tools.find_related_documents(AI_ACTOR, db_session, "F1040.1a")
    assert any(r["type"] == "line" for r in result["results"])
