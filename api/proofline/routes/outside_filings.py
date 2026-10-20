"""B20, C5's last condition. `GET /api/outside-filings` lists the
packet's own outside-filing items with their decided/not-decided status;
`POST /api/outside-filings/{item}/confirm` records a decision.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from proofline.actions.service import perform
from proofline.analysis.outside_filings import outside_filings_report
from proofline.db.connection import get_session
from proofline.packet import load_packet
from proofline.security.actors import Actor
from proofline.security.dependencies import get_current_actor, require_non_client
from proofline.security.redact import redact_for_actor

router = APIRouter()


class ConfirmOutsideFilingRequest(BaseModel):
    decision: str
    note: str


@router.get("/outside-filings")
def get_outside_filings(
    actor: Actor = Depends(require_non_client),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    body = {
        "items": [
            {
                "item": status.item,
                "label": status.label,
                "evidence_refs": list(status.evidence_refs),
                "note": status.note,
                "decided": status.decided,
                "decision": status.decision,
                "decided_by": status.decided_by,
                "decided_note": status.decided_note,
            }
            for status in outside_filings_report(session, packet)
        ]
    }
    return redact_for_actor(actor, packet, body)


@router.post("/outside-filings/{item}/confirm")
def confirm_outside_filing(
    item: str,
    body: ConfirmOutsideFilingRequest,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    result = perform(
        session,
        actor,
        "confirm_outside_filing",
        payload={"item": item, "decision": body.decision, "note": body.note},
        packet=packet,
    )
    return redact_for_actor(actor, packet, result.current_state)
