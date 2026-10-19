"""C5's plain attestation items: `confirm_readiness_item`. Log-only, like
`proofline.actions.sign_offs.confirm_carryover` -- nothing in the packet
can derive "identity verified" or "due diligence done," so there's
nothing to version, just an event recording who confirmed it, when, and
why (`proofline.analysis.readiness.readiness_report` reads it back by
replaying this entity's own events).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from proofline.actions.errors import ActionValidationError, require
from proofline.actions.results import ActionResult
from proofline.analysis.readiness import ATTESTATION_ITEMS
from proofline.db.repository import insert_event
from proofline.packet import Packet
from proofline.security.actors import Actor
from proofline.security.permissions import check_permission


def confirm_readiness_item(
    session: Session,
    actor: Actor,
    *,
    entity_id: str | None,
    expected_revision: int | None,
    payload: dict[str, Any],
    occurred_at: datetime | None,
    packet: Packet | None = None,
) -> ActionResult:
    check_permission(actor, "confirm_readiness_item")
    item = require(payload, "item")
    if item not in ATTESTATION_ITEMS:
        raise ActionValidationError(f"item must be one of {sorted(ATTESTATION_ITEMS)}")
    note = require(payload, "note")
    when = occurred_at or datetime.now(UTC)
    event = insert_event(
        session,
        "readiness_item_confirmed",
        {"item": item, "note": note},
        actor_id=actor.id,
        entity_type="readiness_item",
        entity_id=item,
        revision=None,
        occurred_at=when,
    )
    return ActionResult(
        event=event,
        current_state={
            "item": item,
            "confirmed_by": actor.id,
            "confirmed_at": when.isoformat(),
            "note": note,
            "event_id": str(event.id),
        },
    )
