"""B37: logging time against an area's budget. Log-only, like
`proofline.actions.sign_offs.confirm_carryover` -- a time entry is a fact
nobody edits or compares-and-sets against, so there's no current-state
row, just an event `proofline.analysis.time_tracking` reads back.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from proofline.actions.errors import ActionValidationError, require
from proofline.actions.results import ActionResult
from proofline.analysis.time_tracking import AREA_TO_BUDGET_KEY
from proofline.checks.money import parse_money
from proofline.db.repository import insert_event
from proofline.packet import Packet
from proofline.security.actors import Actor
from proofline.security.permissions import check_permission


def log_time(
    session: Session,
    actor: Actor,
    *,
    entity_id: str | None,
    expected_revision: int | None,
    payload: dict[str, Any],
    occurred_at: datetime | None,
    packet: Packet | None = None,
) -> ActionResult:
    check_permission(actor, "log_time")
    area = require(payload, "area")
    if area not in AREA_TO_BUDGET_KEY:
        raise ActionValidationError(f"area must be one of {sorted(AREA_TO_BUDGET_KEY)}")
    hours = parse_money(payload.get("hours"))
    if hours is None or hours <= 0:
        raise ActionValidationError("hours must be a positive number")
    date = require(payload, "date")
    note = payload.get("note")

    when = occurred_at or datetime.now(UTC)
    entry_id = f"time-{uuid.uuid4()}"
    event = insert_event(
        session,
        "time_logged",
        {"area": area, "hours": hours, "date": date, "note": note},
        actor_id=actor.id,
        entity_type="time_entry",
        entity_id=entry_id,
        revision=None,
        occurred_at=when,
    )
    return ActionResult(
        event=event,
        current_state={
            "event_id": str(event.id),
            "area": area,
            "hours": str(hours),
            "date": date,
            "note": note,
        },
    )
