"""B38: `GET /api/search?q=...`. Staff + AI assistant only -- same guard
as every other staff-surface read (`routes/notifications.py`)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from proofline.analysis.search import search
from proofline.db.connection import get_session
from proofline.packet import load_packet
from proofline.security.actors import Actor
from proofline.security.dependencies import require_non_client
from proofline.security.redact import redact_for_actor

router = APIRouter()


@router.get("/search")
def search_route(
    q: str = Query(default=""),
    actor: Actor = Depends(require_non_client),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    results = search(packet, session, q)
    body = {
        "results": [
            {"type": r.type, "id": r.id, "title": r.title, "snippet": r.snippet}
            for r in results
        ]
    }
    return redact_for_actor(actor, packet, body)
