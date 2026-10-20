from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from proofline.actions.service import perform
from proofline.db.connection import get_session
from proofline.db.repository import list_review_notes
from proofline.packet import load_packet
from proofline.security.actors import Actor
from proofline.security.dependencies import get_current_actor, require_non_client
from proofline.security.redact import redact_for_actor

router = APIRouter()


class AddReviewNoteRequest(BaseModel):
    about_type: str
    about_id: str
    body: str


class RespondReviewNoteRequest(BaseModel):
    expected_revision: int
    body: str


class ResolveReviewNoteRequest(BaseModel):
    expected_revision: int
    resolution: str


@router.get("/review-notes")
def list_notes(
    about_type: str | None = Query(default=None),
    about_id: str | None = Query(default=None),
    actor: Actor = Depends(require_non_client),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    notes = list_review_notes(session, about_type=about_type, about_id=about_id)
    body = {"review_notes": [note.to_dict() for note in notes]}
    return redact_for_actor(actor, packet, body)


@router.post("/review-notes")
def add_note(
    body: AddReviewNoteRequest,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    result = perform(
        session, actor, "add_review_note", payload=body.model_dump(), packet=packet
    )
    return redact_for_actor(actor, packet, result.current_state.to_dict())


@router.post("/review-notes/{note_id}/respond")
def respond_note(
    note_id: str,
    body: RespondReviewNoteRequest,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    result = perform(
        session,
        actor,
        "respond_review_note",
        entity_id=note_id,
        expected_revision=body.expected_revision,
        payload={"body": body.body},
        packet=packet,
    )
    return redact_for_actor(actor, packet, result.current_state.to_dict())


@router.post("/review-notes/{note_id}/resolve")
def resolve_note(
    note_id: str,
    body: ResolveReviewNoteRequest,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    result = perform(
        session,
        actor,
        "resolve_review_note",
        entity_id=note_id,
        expected_revision=body.expected_revision,
        payload={"resolution": body.resolution},
        packet=packet,
    )
    return redact_for_actor(actor, packet, result.current_state.to_dict())
