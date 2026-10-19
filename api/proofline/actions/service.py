"""The one entry point every write goes through:
`perform(session, actor, action, ...)`.

Permission, validation, the current-state compare-and-set and the event
write all happen against the one `session` the caller supplies and is
responsible for committing -- `proofline.db.connection.get_session` commits
at the end of a request only if nothing raised, and rolls back the whole
thing otherwise, so a failure here writes neither the event nor the
current state (CONTRACTS.md Storage, acceptance test I1).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from proofline.actions import check_runs, reveal, review_notes
from proofline.actions.results import ActionResult
from proofline.packet import Packet
from proofline.security.actors import Actor

_HANDLERS = {
    "add_review_note": review_notes.add_review_note,
    "respond_review_note": review_notes.respond_review_note,
    "resolve_review_note": review_notes.resolve_review_note,
    "reveal_sensitive_value": reveal.reveal_sensitive_value,
    "record_check_run": check_runs.record_check_run,
}


def perform(
    session: Session,
    actor: Actor,
    action: str,
    *,
    entity_id: str | None = None,
    expected_revision: int | None = None,
    payload: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
    packet: Packet | None = None,
) -> ActionResult:
    try:
        handler = _HANDLERS[action]
    except KeyError:
        raise ValueError(f"unknown action {action!r}") from None
    return handler(
        session,
        actor,
        entity_id=entity_id,
        expected_revision=expected_revision,
        payload=payload or {},
        occurred_at=occurred_at,
        packet=packet,
    )
