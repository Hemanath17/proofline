from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from proofline.db.models import Event


def insert_event(session: Session, event_type: str, payload: dict) -> Event:
    event = Event(event_type=event_type, payload=payload)
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def get_event(session: Session, event_id: uuid.UUID) -> Event | None:
    return session.get(Event, event_id)
