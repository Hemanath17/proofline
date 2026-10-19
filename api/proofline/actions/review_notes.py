"""The three review-note actions. Real review-note practice, not a
simplified stand-in: only a reviewer, partner or quality reviewer may raise
one; any staff member (preparer included) may respond; only the note's own
author or the partner may resolve it. Clients and the AI assistant can do
none of the three. Open notes blocking filing is recorded by the `status`
field here -- the filing gate itself is C5/Step 8.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from proofline.actions.errors import ActionConflict, ActionValidationError, require
from proofline.actions.results import ActionResult
from proofline.db.models import ReviewNote
from proofline.db.repository import (
    EntityNotFound,
    apply_revision_cas,
    get_review_note,
    insert_event,
    insert_review_note,
)
from proofline.packet import Packet
from proofline.security.actors import Actor
from proofline.security.permissions import check_permission


def add_review_note(
    session: Session,
    actor: Actor,
    *,
    entity_id: str | None,
    expected_revision: int | None,
    payload: dict[str, Any],
    occurred_at: datetime | None,
    packet: Packet | None = None,
) -> ActionResult:
    check_permission(actor, "add_review_note")
    about_type = require(payload, "about_type")
    about_id = require(payload, "about_id")
    body = require(payload, "body")
    note_id = f"note-{uuid.uuid4()}"
    when = occurred_at or datetime.now(UTC)
    note = ReviewNote(
        id=note_id,
        about_type=about_type,
        about_id=about_id,
        opened_by=actor.id,
        opened_at=when,
        status="open",
        revision=1,
        body=body,
    )
    insert_review_note(session, note)
    event = insert_event(
        session,
        "review_note_added",
        {"about_type": about_type, "about_id": about_id, "body": body},
        actor_id=actor.id,
        entity_type="review_note",
        entity_id=note_id,
        revision=1,
        occurred_at=when,
    )
    return ActionResult(event=event, current_state=note)


def respond_review_note(
    session: Session,
    actor: Actor,
    *,
    entity_id: str | None,
    expected_revision: int | None,
    payload: dict[str, Any],
    occurred_at: datetime | None,
    packet: Packet | None = None,
) -> ActionResult:
    check_permission(actor, "respond_review_note")
    if entity_id is None:
        raise ActionValidationError("entity_id is required")
    if expected_revision is None:
        raise ActionValidationError("expected_revision is required")
    note = get_review_note(session, entity_id)
    if note is None:
        raise EntityNotFound(entity_id)
    if note.status == "resolved":
        raise ActionConflict(
            "cannot respond to a resolved note", current=note.to_dict()
        )
    body = require(payload, "body")
    when = occurred_at or datetime.now(UTC)
    updated = apply_revision_cas(
        session, ReviewNote, entity_id, expected_revision, {"body": body}
    )
    event = insert_event(
        session,
        "review_note_responded",
        {"body": body},
        actor_id=actor.id,
        entity_type="review_note",
        entity_id=entity_id,
        revision=updated.revision,
        occurred_at=when,
    )
    return ActionResult(event=event, current_state=updated)


def resolve_review_note(
    session: Session,
    actor: Actor,
    *,
    entity_id: str | None,
    expected_revision: int | None,
    payload: dict[str, Any],
    occurred_at: datetime | None,
    packet: Packet | None = None,
) -> ActionResult:
    if entity_id is None:
        raise ActionValidationError("entity_id is required")
    if expected_revision is None:
        raise ActionValidationError("expected_revision is required")
    note = get_review_note(session, entity_id)
    if note is None:
        raise EntityNotFound(entity_id)
    check_permission(actor, "resolve_review_note", opened_by=note.opened_by)
    resolution = require(payload, "resolution")
    when = occurred_at or datetime.now(UTC)
    updated = apply_revision_cas(
        session,
        ReviewNote,
        entity_id,
        expected_revision,
        {
            "status": "resolved",
            "resolved_by": actor.id,
            "resolved_at": when,
            "resolution": resolution,
        },
    )
    event = insert_event(
        session,
        "review_note_resolved",
        {"resolution": resolution},
        actor_id=actor.id,
        entity_type="review_note",
        entity_id=entity_id,
        revision=updated.revision,
        occurred_at=when,
    )
    return ActionResult(event=event, current_state=updated)
