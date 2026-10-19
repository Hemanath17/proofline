"""C5's readiness view: `GET /api/readiness` and one POST per attestation
item (docs/UX.md's "what blocks" pattern, reused rather than re-decided).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from proofline.actions.service import perform
from proofline.analysis.readiness import readiness_report
from proofline.db.connection import get_session
from proofline.packet import load_packet
from proofline.security.actors import Actor
from proofline.security.dependencies import get_current_actor
from proofline.security.redact import redact_for_actor

router = APIRouter()


class ConfirmReadinessItemRequest(BaseModel):
    note: str


@router.get("/readiness")
def get_readiness(
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    report = readiness_report(session, packet)
    return redact_for_actor(actor, packet, report)


@router.post("/readiness/{item}/confirm")
def confirm_readiness_item(
    item: str,
    body: ConfirmReadinessItemRequest,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    result = perform(
        session,
        actor,
        "confirm_readiness_item",
        payload={"item": item, "note": body.note},
        packet=packet,
    )
    return redact_for_actor(actor, packet, result.current_state)
