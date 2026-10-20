"""B20: deciding one outside-filing item. Log-only, like
`proofline.actions.readiness.confirm_readiness_item` -- nothing in the
packet can derive whether FBAR was actually filed or the 3520 question
resolved, so a staff member records the decision once, read back by
`proofline.analysis.outside_filings.outside_filings_report`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from proofline.actions.errors import ActionValidationError, require
from proofline.actions.results import ActionResult
from proofline.analysis.outside_filings import outside_filing_items
from proofline.db.repository import insert_event
from proofline.packet import Packet
from proofline.security.actors import Actor
from proofline.security.permissions import check_permission

_DECISIONS = frozenset({"filed", "not_required", "client_responsible", "open"})


def confirm_outside_filing(
    session: Session,
    actor: Actor,
    *,
    entity_id: str | None,
    expected_revision: int | None,
    payload: dict[str, Any],
    occurred_at: datetime | None,
    packet: Packet | None = None,
) -> ActionResult:
    if packet is None:
        raise ActionValidationError("confirm_outside_filing needs the packet")
    check_permission(actor, "confirm_outside_filing")
    item = require(payload, "item")
    known_items = {found.item for found in outside_filing_items(packet)}
    if item not in known_items:
        raise ActionValidationError(f"item must be one of {sorted(known_items)}")
    decision = require(payload, "decision")
    if decision not in _DECISIONS:
        raise ActionValidationError(f"decision must be one of {sorted(_DECISIONS)}")
    note = require(payload, "note")

    when = occurred_at or datetime.now(UTC)
    event = insert_event(
        session,
        "outside_filing_decided",
        {"decision": decision, "note": note},
        actor_id=actor.id,
        entity_type="outside_filing",
        entity_id=item,
        revision=None,
        occurred_at=when,
    )
    return ActionResult(
        event=event,
        current_state={
            "item": item,
            "decision": decision,
            "note": note,
            "decided_by": actor.id,
            "event_id": str(event.id),
        },
    )
