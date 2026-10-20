"""Recorded AI suggestions for one case, each labeled "AI-suggested" and
carrying whatever review it's had -- surfaced on `GET /api/cases/{id}`
(routes/cases.py), shown separately from the case's own verified fields,
with no authority of its own (CLAUDE.md).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from proofline.ai.events import AI_SUGGESTION_RECORDED, AI_SUGGESTION_REVIEWED
from proofline.db.repository import list_events_for_entity


def list_case_suggestions(session: Session, case_id: str) -> list[dict]:
    events = list_events_for_entity(session, "case", case_id)

    reviews_by_suggestion: dict[str, list[dict]] = {}
    for event in events:
        if event.event_type != AI_SUGGESTION_REVIEWED:
            continue
        key = event.payload.get("suggestion_event_id")
        reviews_by_suggestion.setdefault(key, []).append(
            {
                "actor_id": event.actor_id,
                "decision": event.payload.get("decision"),
                "proposal_id": event.payload.get("proposal_id"),
                "occurred_at": event.occurred_at.isoformat()
                if event.occurred_at
                else None,
            }
        )

    return [
        {
            "label": "AI-suggested",
            "suggestion_event_id": str(event.id),
            "recorded_at": event.occurred_at.isoformat() if event.occurred_at else None,
            "model": event.payload.get("model"),
            "validation": event.payload.get("validation"),
            "suggestion": event.payload.get("suggestion"),
            "reviews": reviews_by_suggestion.get(str(event.id), []),
        }
        for event in events
        if event.event_type == AI_SUGGESTION_RECORDED
    ]
