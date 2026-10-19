"""Explicit reveal endpoint, for a cleared actor asking to see a sensitive
value outside a document page (e.g. a household field) -- the document
page route (routes/documents.py) calls the same `reveal_sensitive_value`
action itself for values embedded in `printed_content`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from proofline.actions.service import perform
from proofline.db.connection import get_session
from proofline.packet import load_packet
from proofline.security.actors import Actor
from proofline.security.dependencies import get_current_actor

router = APIRouter()


class RevealRequest(BaseModel):
    entity_id: str
    reason: str
    field: str | None = None


@router.post("/reveal")
def reveal(
    body: RevealRequest,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    result = perform(
        session,
        actor,
        "reveal_sensitive_value",
        entity_id=body.entity_id,
        payload={"reason": body.reason, "field": body.field},
        packet=packet,
    )
    return {"event_id": str(result.event.id)}
