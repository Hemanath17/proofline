"""B19: judgments and elections. `GET /api/judgments` lists every one
recorded; `POST /api/judgments` records a new one. `GET /api/due-diligence`
is the Form 8867 checklist (Part G), whose "done" status is the existing
`due_diligence_done` readiness attestation.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from proofline.actions.service import perform
from proofline.analysis.due_diligence import due_diligence_checklist
from proofline.analysis.judgments import list_judgments
from proofline.analysis.readiness import attestation_item
from proofline.db.connection import get_session
from proofline.packet import load_packet
from proofline.security.actors import Actor
from proofline.security.dependencies import get_current_actor, require_non_client
from proofline.security.redact import redact_for_actor

router = APIRouter()


class RecordJudgmentRequest(BaseModel):
    authority: str
    approved_by: str
    reasoning: str
    claim_key: str | None = None
    is_election: bool = False
    what_if_id: str | None = None
    case_id: str | None = None


@router.get("/judgments")
def list_judgments_route(
    actor: Actor = Depends(require_non_client),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    body = {
        "judgments": [
            {
                "id": j.id,
                "recorded_by": j.recorded_by,
                "authority": j.authority,
                "approved_by": j.approved_by,
                "reasoning": j.reasoning,
                "claim_key": j.claim_key,
                "is_election": j.is_election,
                "what_if_id": j.what_if_id,
                "case_id": j.case_id,
                "occurred_at": j.occurred_at,
            }
            for j in list_judgments(session)
        ]
    }
    return redact_for_actor(actor, packet, body)


@router.post("/judgments")
def record_judgment(
    body: RecordJudgmentRequest,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    result = perform(
        session,
        actor,
        "record_judgment_election",
        payload=body.model_dump(),
        packet=packet,
    )
    return redact_for_actor(actor, packet, result.current_state)


@router.get("/due-diligence")
def get_due_diligence(
    actor: Actor = Depends(require_non_client),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    done = attestation_item(session, "due_diligence_done", "Due diligence done")
    body = {
        "checklist": due_diligence_checklist(packet),
        "done": done.met,
        "confirmed_by": done.confirmed_by,
        "confirmed_at": done.confirmed_at,
        "note": done.note,
    }
    return redact_for_actor(actor, packet, body)
