from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, TypeVar

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from proofline.db.canonical import prepare_payload_for_storage
from proofline.db.models import CheckRun, Event, ReviewNote

_Model = TypeVar("_Model", ReviewNote, CheckRun)


class StaleRevision(Exception):
    """Raised when a compare-and-set update's WHERE clause matched no row
    because the caller's `expected_revision` is no longer current. Carries
    the row as it actually stands now, so the caller can return it in a 409
    (redacted for whoever's asking) per CONTRACTS.md and acceptance test
    I2."""

    def __init__(self, current: Any):
        self.current = current


class EntityNotFound(Exception):
    """Raised when a compare-and-set update's WHERE clause matched no row
    because no row with that id exists at all -- distinct from a stale
    revision, which means the row exists but has moved on."""


def _needs_sqlite_seq_placeholder(session: Session) -> bool:
    """True only for the SQLite test fixtures. SQLite has no equivalent to
    Postgres's identity column, so it can't generate `seq` itself -- every
    other dialect (postgresql in production) must rely on the database's
    own identity sequence, never on application code, to assign `seq`. This
    is the one place that decides which case applies, kept as its own
    function so that decision is tested directly rather than trusted by
    inspection."""
    return session.get_bind().dialect.name == "sqlite"


def insert_event(
    session: Session,
    event_type: str,
    payload: dict,
    *,
    actor_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    revision: int | None = None,
    occurred_at: datetime | None = None,
    schema_version: int = 1,
) -> Event:
    """Writes one event. `payload` is run through
    `prepare_payload_for_storage` first, so a caller building a payload out
    of domain objects (which naturally carry `Decimal`) never has to
    remember to convert it -- every event gets this for free.

    Does not commit: callers inside the action service share one
    transaction with their current-state write and must commit or roll
    back together (I1). A bare call from a test is responsible for its own
    commit, same as before.
    """
    event = Event(
        event_type=event_type,
        payload=prepare_payload_for_storage(payload),
        actor_id=actor_id,
        entity_type=entity_type,
        entity_id=entity_id,
        revision=revision,
        occurred_at=occurred_at,
        schema_version=schema_version,
    )
    if _needs_sqlite_seq_placeholder(session):
        # A fixed placeholder satisfies the NOT NULL constraint; nothing
        # reads this column's value yet.
        event.seq = 0
    session.add(event)
    session.flush()
    return event


def get_event(session: Session, event_id: uuid.UUID) -> Event | None:
    return session.get(Event, event_id)


def apply_revision_cas(
    session: Session,
    model: type[_Model],
    pk_value: str,
    expected_revision: int,
    values: dict[str, Any],
) -> _Model:
    """UPDATE ... WHERE id = :pk_value AND revision = :expected_revision,
    bumping `revision` by one and setting `values` in the same statement.
    This is the single SQL statement that makes the compare-and-set
    atomic: two callers racing on the same row can each only ever match it
    while its revision is still `expected_revision`, so at most one UPDATE
    can succeed (`rowcount == 1`); the other's `rowcount` comes back 0,
    with no error and no partial write (acceptance test I2).

    Raises `EntityNotFound` if no row with that id exists at all, or
    `StaleRevision(current)` if the row exists but had already moved past
    `expected_revision`.
    """
    result = session.execute(
        update(model)
        .where(model.id == pk_value, model.revision == expected_revision)
        .values(revision=expected_revision + 1, **values)
        # Explicit, rather than relying on "auto"/"evaluate" to update any
        # already-loaded copy of this row in the session's identity map --
        # confirmed by hand that "evaluate" can silently sync some of a
        # multi-column SET onto a cached object but not others. Refreshing
        # from the database below is the one way that's actually reliable.
        .execution_options(synchronize_session=False)
    )
    if result.rowcount == 1:
        session.flush()
        row = session.get(model, pk_value)
        session.refresh(row)
        return row  # type: ignore[return-value]
    current = session.get(model, pk_value)
    if current is None:
        raise EntityNotFound(pk_value)
    session.refresh(current)
    raise StaleRevision(current)


def insert_review_note(session: Session, note: ReviewNote) -> ReviewNote:
    session.add(note)
    session.flush()
    return note


def get_review_note(session: Session, note_id: str) -> ReviewNote | None:
    return session.get(ReviewNote, note_id)


def list_review_notes(
    session: Session, *, about_type: str | None = None, about_id: str | None = None
) -> list[ReviewNote]:
    statement = select(ReviewNote).order_by(ReviewNote.opened_at)
    if about_type is not None:
        statement = statement.where(ReviewNote.about_type == about_type)
    if about_id is not None:
        statement = statement.where(ReviewNote.about_id == about_id)
    return list(session.scalars(statement))


def insert_check_run(session: Session, check_run: CheckRun) -> CheckRun:
    session.add(check_run)
    session.flush()
    return check_run
