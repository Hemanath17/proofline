"""S5: the client workspace. A genuinely smaller API surface, not the
staff UI with fewer buttons -- `require_client` keeps every route here
client-only; signing is the existing `POST /api/filing/authorize`
(CONTRACTS.md C5), not a second signing mechanism.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from proofline.analysis.client_workspace import (
    client_changes,
    client_documents,
    client_package_summary,
    client_questions,
    client_summary,
)
from proofline.db.connection import get_session
from proofline.db.repository import record_last_seen
from proofline.packet import load_packet
from proofline.security.actors import Actor
from proofline.security.dependencies import require_client
from proofline.security.redact import redact_for_actor

router = APIRouter()


@router.get("/client/summary")
def get_client_summary(
    actor: Actor = Depends(require_client),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    record_last_seen(session, actor.id, "client_summary", "summary", datetime.now(UTC))
    return redact_for_actor(actor, packet, client_summary(session, packet))


@router.get("/client/questions")
def get_client_questions(
    actor: Actor = Depends(require_client),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    threads = client_questions(session, packet)
    for thread in threads:
        record_last_seen(
            session, actor.id, "case", thread["case_id"], datetime.now(UTC)
        )
    return redact_for_actor(actor, packet, {"threads": threads})


@router.get("/client/documents")
def get_client_documents(
    actor: Actor = Depends(require_client),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    return redact_for_actor(
        actor, packet, {"documents": client_documents(session, packet)}
    )


@router.get("/client/changes")
def get_client_changes(
    actor: Actor = Depends(require_client),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    return redact_for_actor(
        actor, packet, {"changed": client_changes(session, packet, actor)}
    )


@router.get("/client/package")
def get_client_package(
    actor: Actor = Depends(require_client),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    return redact_for_actor(actor, packet, client_package_summary(session, packet))
