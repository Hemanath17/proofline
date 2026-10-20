"""`proofline/ai/events.py` and `proofline/ai/suggestions.py`: the
`ai_suggestion_recorded`/`ai_suggestion_reviewed` events are the real
audit record (CLAUDE.md), separate from any Langfuse trace -- written
through the normal `insert_event` path, no migration involved."""

from __future__ import annotations

from proofline.ai import events as ai_events
from proofline.ai.suggestions import list_case_suggestions
from proofline.security.actors import AI_ASSISTANT_ID
from sqlalchemy.orm import Session


def test_record_suggestion_writes_the_expected_event(db_session: Session) -> None:
    event = ai_events.record_suggestion(
        db_session,
        case_id="case-1",
        model_name="llama-3.3-70b-versatile",
        prompt_version=1,
        schema_version=1,
        tool_calls=[{"name": "open_case", "args": {"case_id": "case-1"}}],
        validation_ok=True,
        validation_reasons=(),
        suggestion={"summary": "x", "confidence": "supported"},
    )
    db_session.commit()

    assert event.event_type == ai_events.AI_SUGGESTION_RECORDED
    assert event.actor_id == AI_ASSISTANT_ID
    assert event.entity_type == "case"
    assert event.entity_id == "case-1"
    assert event.revision is None
    assert event.payload["model"] == "llama-3.3-70b-versatile"
    assert event.payload["validation"] == {"ok": True, "reasons": []}


def test_record_review_references_the_suggestion_event(db_session: Session) -> None:
    suggestion_event = ai_events.record_suggestion(
        db_session,
        case_id="case-1",
        model_name="m",
        prompt_version=1,
        schema_version=1,
        tool_calls=[],
        validation_ok=True,
        validation_reasons=(),
        suggestion={"summary": "x", "confidence": "supported"},
    )
    db_session.flush()

    review_event = ai_events.record_review(
        db_session,
        case_id="case-1",
        suggestion_event_id=suggestion_event.id,
        actor_id="st-01",
        decision="accept",
        resolution_type="mark_legitimate",
        fields={"reason": "expected"},
        evidence_refs=["D01"],
        proposal_id="proposal-1",
    )
    db_session.commit()

    assert review_event.event_type == ai_events.AI_SUGGESTION_REVIEWED
    assert review_event.payload["suggestion_event_id"] == str(suggestion_event.id)
    assert review_event.payload["decision"] == "accept"
    assert review_event.payload["proposal_id"] == "proposal-1"


def test_list_case_suggestions_joins_the_review(db_session: Session) -> None:
    suggestion_event = ai_events.record_suggestion(
        db_session,
        case_id="case-2",
        model_name="m",
        prompt_version=1,
        schema_version=1,
        tool_calls=[],
        validation_ok=False,
        validation_reasons=("cited claim 'x' doesn't belong to case case-2",),
        suggestion={"summary": "x", "confidence": "uncertain"},
    )
    db_session.flush()
    ai_events.record_review(
        db_session,
        case_id="case-2",
        suggestion_event_id=suggestion_event.id,
        actor_id="st-01",
        decision="reject",
    )
    db_session.commit()

    suggestions = list_case_suggestions(db_session, "case-2")
    assert len(suggestions) == 1
    assert suggestions[0]["label"] == "AI-suggested"
    assert suggestions[0]["validation"]["ok"] is False
    assert suggestions[0]["reviews"] == [
        {
            "actor_id": "st-01",
            "decision": "reject",
            "proposal_id": None,
            "occurred_at": suggestions[0]["reviews"][0]["occurred_at"],
        }
    ]


def test_list_case_suggestions_empty_for_an_uninvestigated_case(
    db_session: Session,
) -> None:
    assert list_case_suggestions(db_session, "case-never-investigated") == []
