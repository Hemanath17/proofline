"""B37: time against budget. `GET /api/time` reports logged vs. the
packet's own budget per area; `POST /api/time` logs one entry.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from proofline.actions.service import perform
from proofline.analysis.time_tracking import list_time_entries, time_budget_report
from proofline.db.connection import get_session
from proofline.packet import load_packet
from proofline.security.actors import Actor
from proofline.security.dependencies import get_current_actor, require_non_client
from proofline.security.redact import redact_for_actor

router = APIRouter()


class LogTimeRequest(BaseModel):
    area: str
    hours: str
    date: str
    note: str | None = None


@router.get("/time")
def get_time_report(
    actor: Actor = Depends(require_non_client),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    body = {
        "budget": [
            {
                "area": row.area,
                "budget_hours": str(row.budget_hours) if row.budget_hours else None,
                "logged_hours": str(row.logged_hours),
                "over_budget": row.over_budget,
            }
            for row in time_budget_report(session, packet)
        ],
        "entries": [
            {
                "event_id": entry.event_id,
                "actor_id": entry.actor_id,
                "area": entry.area,
                "hours": str(entry.hours),
                "date": entry.date,
                "note": entry.note,
            }
            for entry in list_time_entries(session)
        ],
    }
    return redact_for_actor(actor, packet, body)


@router.post("/time")
def log_time(
    body: LogTimeRequest,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    result = perform(
        session, actor, "log_time", payload=body.model_dump(), packet=packet
    )
    return redact_for_actor(actor, packet, result.current_state)
