"""Replays every event, in `seq` order, into fresh current-state tables.

Migrations change the shape of tables; this replays the facts back into
them. Rebuilding after a migration must give exactly the state that was
already stored (CONTRACTS.md Storage, acceptance test I5) -- this module is
also how that gets checked, by comparing its output against the live
tables `proofline.actions.service.perform` built one action at a time.

Each event type is replayed by a handler keyed on `(event_type,
schema_version)`, so a future change to an event's payload shape can add a
new handler for the new `schema_version` without breaking how an old event
is read (CONTRACTS.md: "`rebuild.py` knows how to read the old versions, so
old events stay valid forever"). An event with no matching handler --
Step 1's throwaway "test_event" rows, or a log-only event type that has no
current-state row at all (`sensitive_value_revealed`) -- is read and
skipped, not an error.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeAlias

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from proofline.db.models import CheckRun, Event, ReviewNote

_Handler: TypeAlias = Callable[[Session, Event], None]
_HANDLERS: dict[tuple[str, int], _Handler] = {}


def _register(
    event_type: str, schema_version: int = 1
) -> Callable[[_Handler], _Handler]:
    def decorator(handler: _Handler) -> _Handler:
        _HANDLERS[(event_type, schema_version)] = handler
        return handler

    return decorator


@_register("review_note_added")
def _replay_review_note_added(session: Session, event: Event) -> None:
    session.add(
        ReviewNote(
            id=event.entity_id,
            about_type=event.payload["about_type"],
            about_id=event.payload["about_id"],
            opened_by=event.actor_id,
            opened_at=event.occurred_at,
            status="open",
            revision=event.revision,
        )
    )


@_register("review_note_responded")
def _replay_review_note_responded(session: Session, event: Event) -> None:
    note = session.get(ReviewNote, event.entity_id)
    if note is not None:
        note.revision = event.revision


@_register("review_note_resolved")
def _replay_review_note_resolved(session: Session, event: Event) -> None:
    note = session.get(ReviewNote, event.entity_id)
    if note is not None:
        note.status = "resolved"
        note.resolved_by = event.actor_id
        note.resolved_at = event.occurred_at
        note.resolution = event.payload.get("resolution")
        note.revision = event.revision


@_register("check_run_recorded")
def _replay_check_run_recorded(session: Session, event: Event) -> None:
    session.add(
        CheckRun(
            id=event.entity_id,
            event_id=event.id,
            return_version=event.payload["return_version"],
            findings=event.payload["findings"],
            failures=event.payload["failures"],
        )
    )


def rebuild_current_state(session: Session) -> None:
    """Clears every current-state table this module knows how to rebuild,
    then replays the full event history back into them, in `seq` order."""
    session.execute(delete(ReviewNote))
    session.execute(delete(CheckRun))
    session.flush()
    for event in session.scalars(select(Event).order_by(Event.seq)):
        handler = _HANDLERS.get((event.event_type, event.schema_version))
        if handler is not None:
            handler(session, event)
    session.flush()
