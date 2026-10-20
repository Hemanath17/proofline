"""B19: recording a judgment or election. Log-only, like
`proofline.actions.outside_filings.confirm_outside_filing` -- an election
such as section 179 is a fact about what was decided and relied on, never
edited afterward; a later change is a new record, not an update to this
one.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from proofline.actions.errors import ActionValidationError, require
from proofline.actions.results import ActionResult
from proofline.db.repository import insert_event
from proofline.packet import Packet
from proofline.security.actors import Actor
from proofline.security.permissions import check_permission


def record_judgment_election(
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
        raise ActionValidationError("record_judgment_election needs the packet")
    check_permission(actor, "record_judgment_election")
    authority = require(payload, "authority")
    approved_by = require(payload, "approved_by")
    reasoning = require(payload, "reasoning")
    claim_key = payload.get("claim_key")
    is_election = bool(payload.get("is_election", False))
    what_if_id = payload.get("what_if_id")
    case_id = payload.get("case_id")

    if is_election:
        if not what_if_id:
            raise ActionValidationError(
                "an election needs what_if_id (which packet alternative it's tied to)"
            )
        try:
            packet.what_if.alternative(what_if_id)
        except KeyError:
            raise ActionValidationError(
                f"no what-if alternative {what_if_id!r} in the packet"
            ) from None

    when = occurred_at or datetime.now(UTC)
    judgment_id = f"judgment-{uuid.uuid4()}"
    event = insert_event(
        session,
        "judgment_election_recorded",
        {
            "authority": authority,
            "approved_by": approved_by,
            "reasoning": reasoning,
            "claim_key": claim_key,
            "is_election": is_election,
            "what_if_id": what_if_id,
            "case_id": case_id,
        },
        actor_id=actor.id,
        entity_type="judgment",
        entity_id=judgment_id,
        revision=None,
        occurred_at=when,
    )
    return ActionResult(
        event=event,
        current_state={
            "id": judgment_id,
            "authority": authority,
            "approved_by": approved_by,
            "reasoning": reasoning,
            "claim_key": claim_key,
            "is_election": is_election,
            "what_if_id": what_if_id,
            "case_id": case_id,
            "event_id": str(event.id),
        },
    )
