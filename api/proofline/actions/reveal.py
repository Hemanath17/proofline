"""Revealing a sensitive value to a cleared actor. Log-only: there's
nothing to version, so there's no current-state row and no revision
check -- just an event, which is the view-log entry itself (CONTRACTS.md
Redaction: "every unmasked view writes a view-log event"). A reveal with
no stated reason isn't a usable audit trail, so `reason` is required and
saved on the event, same as every other typed free-text field an action
needs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from proofline.actions.errors import ActionValidationError, require
from proofline.actions.results import ActionResult
from proofline.db.repository import insert_event
from proofline.packet import Packet
from proofline.security.actors import Actor
from proofline.security.permissions import check_permission


def reveal_sensitive_value(
    session: Session,
    actor: Actor,
    *,
    entity_id: str | None,
    expected_revision: int | None,
    payload: dict[str, Any],
    occurred_at: datetime | None,
    packet: Packet | None = None,
) -> ActionResult:
    check_permission(actor, "reveal_sensitive_value")
    if entity_id is None:
        raise ActionValidationError(
            "entity_id (the packet reference to the sensitive value, e.g. "
            "'household:theo' or 'ev-0012') is required"
        )
    reason = require(payload, "reason")
    field = payload.get("field")
    when = occurred_at or datetime.now(UTC)
    event_payload: dict[str, Any] = {"reason": reason}
    if field:
        event_payload["field"] = field
    event = insert_event(
        session,
        "sensitive_value_revealed",
        event_payload,
        actor_id=actor.id,
        entity_type="sensitive_value",
        entity_id=entity_id,
        revision=None,
        occurred_at=when,
    )
    return ActionResult(event=event, current_state=None)
