"""The two AI provenance events (CLAUDE.md: AI output "is stored as an AI
provenance event"). No migration needed -- `events.payload` is already a
free JSON column and `event_type` a free string.

`ai_suggestion_recorded`: written once per `POST /investigate` call, by
the `ai-assistant` actor, holding the model, prompt/schema version, the
case investigated, the tool calls made (names + args, never full tool
outputs), the validator's result and the raw suggestion.

`ai_suggestion_reviewed`: written once a person accepts, edits or rejects
a recorded suggestion, referencing the first event's id. Never a second
`ai_suggestion_recorded` is edited or replaced -- undo is a new event,
same rule as everything else in this app (CLAUDE.md).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from proofline.db.models import Event
from proofline.db.repository import insert_event
from proofline.security.actors import AI_ASSISTANT_ID

AI_SUGGESTION_RECORDED = "ai_suggestion_recorded"
AI_SUGGESTION_REVIEWED = "ai_suggestion_reviewed"


def record_suggestion(
    session: Session,
    *,
    case_id: str,
    model_name: str,
    prompt_version: int,
    schema_version: int,
    tool_calls: list[dict[str, Any]],
    validation_ok: bool,
    validation_reasons: tuple[str, ...],
    suggestion: dict[str, Any],
) -> Event:
    return insert_event(
        session,
        AI_SUGGESTION_RECORDED,
        {
            "model": model_name,
            "prompt_version": prompt_version,
            "schema_version": schema_version,
            "case_id": case_id,
            "tool_calls": tool_calls,
            "validation": {"ok": validation_ok, "reasons": list(validation_reasons)},
            "suggestion": suggestion,
        },
        actor_id=AI_ASSISTANT_ID,
        entity_type="case",
        entity_id=case_id,
        revision=None,
    )


def record_review(
    session: Session,
    *,
    case_id: str,
    suggestion_event_id: UUID,
    actor_id: str,
    decision: str,
    resolution_type: str | None = None,
    fields: dict[str, Any] | None = None,
    evidence_refs: list[str] | None = None,
    proposal_id: str | None = None,
) -> Event:
    return insert_event(
        session,
        AI_SUGGESTION_REVIEWED,
        {
            "suggestion_event_id": str(suggestion_event_id),
            "decision": decision,
            "resolution_type": resolution_type,
            "fields": fields,
            "evidence_refs": evidence_refs,
            "proposal_id": proposal_id,
        },
        actor_id=actor_id,
        entity_type="case",
        entity_id=case_id,
        revision=None,
    )
