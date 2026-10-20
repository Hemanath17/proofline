"""The Evidence Investigator's own two routes (Step 10, Part 1):
- `POST /api/cases/{case_id}/investigate` runs one investigation and
  records it as an `ai_suggestion_recorded` event. It never writes a case
  proposal itself.
- `POST /api/cases/{case_id}/suggestions/{suggestion_event_id}/review`
  is the one way a person turns a recorded suggestion into a real
  proposal (by calling the existing `submit_proposal` action, exactly as
  a manually-typed proposal would), or rejects it outright. Either way, a
  second `ai_suggestion_reviewed` event records the decision.

Both are staff-only (`require_non_client`) -- the AI assistant triggers
neither itself.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from proofline.actions.service import perform
from proofline.ai import events as ai_events
from proofline.ai import tracing
from proofline.ai.investigator import (
    PROMPT_VERSION,
    InvestigatorConfigError,
    investigate_case,
    is_enabled,
)
from proofline.ai.investigator import (
    model_name as investigator_model_name,
)
from proofline.ai.schema import SCHEMA_VERSION
from proofline.ai.validator import validate_suggestion
from proofline.db.connection import get_session
from proofline.db.repository import get_case, get_event, list_case_proposals
from proofline.packet import load_packet
from proofline.security.actors import Actor
from proofline.security.dependencies import require_non_client
from proofline.security.permissions import check_permission
from proofline.security.redact import redact_for_actor

router = APIRouter()


@router.post("/cases/{case_id}/investigate")
def investigate(
    case_id: str,
    actor: Actor = Depends(require_non_client),
    session: Session = Depends(get_session),
) -> dict:
    check_permission(actor, "trigger_investigation")
    packet = load_packet()
    case = get_case(session, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="not found")
    if not is_enabled():
        raise HTTPException(
            status_code=503,
            detail=(
                "the Evidence Investigator is not enabled "
                "(AI_INVESTIGATOR_ENABLED is not 'true')"
            ),
        )

    try:
        with tracing.trace_investigation(
            actor=actor,
            case_id=case_id,
            model_name=investigator_model_name(),
            prompt_version=PROMPT_VERSION,
        ) as trace_record:
            run = investigate_case(session, case_id)
            trace_record["tool_calls"] = run.tool_calls
            trace_record["summary"] = run.suggestion.summary
            trace_record["confidence"] = run.suggestion.confidence
    except InvestigatorConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None

    result = validate_suggestion(packet, case, run.suggestion)
    suggestion = run.suggestion
    if not result.ok:
        suggestion = suggestion.model_copy(update={"confidence": "uncertain"})

    event = ai_events.record_suggestion(
        session,
        case_id=case_id,
        model_name=run.model_name,
        prompt_version=PROMPT_VERSION,
        schema_version=SCHEMA_VERSION,
        tool_calls=run.tool_calls,
        validation_ok=result.ok,
        validation_reasons=result.reasons,
        suggestion=suggestion.model_dump(mode="json"),
    )

    body = {
        "suggestion_event_id": str(event.id),
        "suggestion": suggestion.model_dump(mode="json"),
        "validation": {"ok": result.ok, "reasons": list(result.reasons)},
    }
    return redact_for_actor(actor, packet, body)


class SuggestionReviewRequest(BaseModel):
    decision: Literal["accept", "edit", "reject"]
    expected_revision: int | None = None
    resolution_type: str | None = None
    fields: dict[str, Any] | None = None
    evidence_refs: list[str] | None = None


@router.post("/cases/{case_id}/suggestions/{suggestion_event_id}/review")
def review_suggestion(
    case_id: str,
    suggestion_event_id: str,
    body: SuggestionReviewRequest,
    actor: Actor = Depends(require_non_client),
    session: Session = Depends(get_session),
) -> dict:
    check_permission(actor, "review_ai_suggestion")
    packet = load_packet()
    case = get_case(session, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="not found")

    try:
        event_uuid = uuid.UUID(suggestion_event_id)
    except ValueError:
        raise HTTPException(
            status_code=422, detail="not a valid suggestion id"
        ) from None
    suggestion_event = get_event(session, event_uuid)
    if (
        suggestion_event is None
        or suggestion_event.event_type != ai_events.AI_SUGGESTION_RECORDED
        or suggestion_event.entity_id != case_id
    ):
        raise HTTPException(
            status_code=404, detail="suggestion not found for this case"
        )

    suggestion = suggestion_event.payload["suggestion"]
    proposal_id: str | None = None

    if body.decision in ("accept", "edit"):
        if body.expected_revision is None:
            raise HTTPException(
                status_code=422,
                detail="expected_revision is required to accept or edit",
            )
        resolution_type = body.resolution_type or suggestion["proposed_resolution_type"]
        fields = (
            body.fields if body.fields is not None else suggestion["proposed_fields"]
        )
        evidence_refs = (
            body.evidence_refs
            if body.evidence_refs is not None
            else [*suggestion["cited_claim_ids"], *suggestion["cited_document_ids"]]
        )
        perform(
            session,
            actor,
            "submit_proposal",
            entity_id=case_id,
            expected_revision=body.expected_revision,
            payload={
                "resolution_type": resolution_type,
                "fields": fields,
                "evidence_refs": evidence_refs,
            },
            packet=packet,
        )
        proposals = list_case_proposals(session, case_id)
        proposal_id = proposals[-1].id if proposals else None
        review_event = ai_events.record_review(
            session,
            case_id=case_id,
            suggestion_event_id=event_uuid,
            actor_id=actor.id,
            decision=body.decision,
            resolution_type=resolution_type,
            fields=fields,
            evidence_refs=evidence_refs,
            proposal_id=proposal_id,
        )
    else:
        review_event = ai_events.record_review(
            session,
            case_id=case_id,
            suggestion_event_id=event_uuid,
            actor_id=actor.id,
            decision="reject",
        )

    updated_case = get_case(session, case_id)
    body_out = {
        "review_event_id": str(review_event.id),
        "proposal_id": proposal_id,
        "case": updated_case.to_dict() if updated_case is not None else None,
    }
    return redact_for_actor(actor, packet, body_out)
