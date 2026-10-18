from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from proofline.db.models import Event


def _needs_sqlite_seq_placeholder(session: Session) -> bool:
    """True only for the SQLite test fixtures. SQLite has no equivalent to
    Postgres's identity column, so it can't generate `seq` itself -- every
    other dialect (postgresql in production) must rely on the database's
    own identity sequence, never on application code, to assign `seq`. This
    is the one place that decides which case applies, kept as its own
    function so that decision is tested directly rather than trusted by
    inspection."""
    return session.get_bind().dialect.name == "sqlite"


def insert_event(session: Session, event_type: str, payload: dict) -> Event:
    event = Event(event_type=event_type, payload=payload)
    if _needs_sqlite_seq_placeholder(session):
        # A fixed placeholder satisfies the NOT NULL constraint; nothing
        # reads this column's value yet.
        event.seq = 0
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def get_event(session: Session, event_id: uuid.UUID) -> Event | None:
    return session.get(Event, event_id)
