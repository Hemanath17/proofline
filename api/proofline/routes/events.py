from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from proofline.db.connection import get_session
from proofline.db.repository import get_event, insert_event

router = APIRouter()


class EventCreate(BaseModel):
    event_type: str
    payload: dict


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: str
    payload: dict
    created_at: datetime
    schema_version: int


@router.post("/events", response_model=EventOut)
def create_event(body: EventCreate, session: Session = Depends(get_session)) -> EventOut:
    event = insert_event(session, body.event_type, body.payload)
    return EventOut.model_validate(event)


@router.get("/events/{event_id}", response_model=EventOut)
def read_event(event_id: uuid.UUID, session: Session = Depends(get_session)) -> EventOut:
    event = get_event(session, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    return EventOut.model_validate(event)
