"""B14, B26: the notifications feed. Staff + AI assistant only -- the
client has its own "what changed" view (`routes/client.py`)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from proofline.analysis.notifications import notifications_report
from proofline.db.connection import get_session
from proofline.packet import load_packet
from proofline.security.actors import Actor
from proofline.security.dependencies import require_non_client
from proofline.security.redact import redact_for_actor

router = APIRouter()


@router.get("/notifications")
def get_notifications(
    actor: Actor = Depends(require_non_client),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    report = notifications_report(session, packet, actor)
    return redact_for_actor(actor, packet, report)
