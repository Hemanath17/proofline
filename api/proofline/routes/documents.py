"""`/documents` and one rendered page. A cleared actor who requests a page
that actually contains a sensitive value gets it unmasked, and that's
logged as a reveal (one `reveal_sensitive_value` action per value found) --
an uncleared actor gets masked text and nothing is logged, because nothing
was revealed.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from proofline.actions.service import perform
from proofline.db.connection import get_session
from proofline.packet import load_packet
from proofline.security.actors import Actor
from proofline.security.dependencies import get_current_actor
from proofline.security.redact import (
    collect_sensitive_values,
    redact_for_actor,
    values_present_in,
)

router = APIRouter()


@router.get("/documents")
def list_documents(actor: Actor = Depends(get_current_actor)) -> dict:
    packet = load_packet()
    documents = [
        {
            "id": document.id,
            "title": document.title,
            "document_type": document.document_type,
            "issuer": document.issuer,
            "tax_year": document.tax_year,
            "received_at": document.received_at,
            "page_count": document.page_count,
            "marked_corrected": document.marked_corrected,
        }
        for document in packet.documents
    ]
    return redact_for_actor(actor, packet, {"documents": documents})


@router.get("/documents/{document_id}/pages/{page_number}")
def get_document_page(
    document_id: str,
    page_number: int,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    try:
        document = packet.document(document_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="document not found") from None
    page = next((p for p in document.pages if p.page == page_number), None)
    if page is None:
        raise HTTPException(status_code=404, detail="page not found")

    body = {
        "document_id": document_id,
        "page": page_number,
        "printed_content": page.printed_content,
    }
    if not actor.clearance:
        return redact_for_actor(actor, packet, body)

    sensitive_values = collect_sensitive_values(packet)
    for found in values_present_in(page.printed_content, sensitive_values):
        perform(
            session,
            actor,
            "reveal_sensitive_value",
            entity_id=f"doc:{document_id}#page{page_number}",
            payload={
                "field": found.category,
                "reason": f"viewing document {document_id} page {page_number}",
            },
            packet=packet,
        )
    return body
