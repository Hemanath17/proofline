"""C5's package, its authorization and submission, and the post-filing
Letter 566 pack (CONTRACTS.md C5, acceptance test A3).

Authorization events carry e-file signature PINs -- sensitive, masked
for an uncleared actor the same way every other sensitive value is.
Unlike an SSN or account number, a PIN here is *recorded by this system*
(through `authorize_filing`) rather than only ever read from the packet,
so `collect_sensitive_values(packet)` alone isn't enough: a reviewer-agent
pass found that a PIN not already present in the packet's own `tl-20`
timeline text (e.g. a different household's PINs) came back unmasked.
`_pin_sensitive_values` adds every PIN this system has ever recorded,
read from the `filing_authorized` events themselves, to the known-value
list for any response that might actually contain one. A cleared actor
who asks for the authorization history and the PINs are actually present
in it gets the same reveal-and-log treatment as `routes/documents.py`'s
rendered page: one `reveal_sensitive_value` per PIN actually shown.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from proofline.actions.service import perform
from proofline.analysis.calculation import adjustments_by_claim
from proofline.analysis.filing import build_package, letter_566_pack, package_to_dict
from proofline.db.connection import get_session
from proofline.db.repository import (
    list_adjustments,
    list_events_by_type,
    list_events_for_entity,
    list_filed_records,
)
from proofline.packet import load_packet
from proofline.security.actors import Actor
from proofline.security.dependencies import get_current_actor
from proofline.security.redact import (
    SensitiveValue,
    collect_sensitive_values,
    redact_for_actor,
    redact_json,
)

router = APIRouter()

_JURISDICTIONS = ("federal", "california")


class AuthorizeFilingRequest(BaseModel):
    pins: dict[str, str]


class SubmitFilingRequest(BaseModel):
    package_reference: str
    status: str
    codes: list[dict[str, Any]] = []
    submission_id: str | None = None


def _require_jurisdiction(jurisdiction: str) -> str:
    if jurisdiction not in _JURISDICTIONS:
        raise HTTPException(
            status_code=404, detail=f"unknown jurisdiction {jurisdiction!r}"
        )
    return jurisdiction


def _pin_sensitive_values(session: Session) -> list[SensitiveValue]:
    """Every PIN this system has ever recorded through `authorize_filing`
    -- unlike an SSN, a PIN here has no guarantee of also appearing in
    the packet's own text, so it can't rely on `collect_sensitive_values`
    alone (see this module's docstring)."""
    return [
        SensitiveValue(str(pin), "efile_pin")
        for event in list_events_by_type(session, "filing_authorized")
        for pin in event.payload.get("pins", {}).values()
    ]


def _redact_filing_response(actor: Actor, packet, session: Session, data: Any) -> Any:
    """Like `redact_for_actor`, but for a response that may contain a
    PIN: the known-sensitive-value list is extended with every recorded
    PIN, not just the packet's own."""
    if actor.clearance:
        return data
    return redact_json(
        data, collect_sensitive_values(packet) + _pin_sensitive_values(session)
    )


@router.get("/filing/package")
def get_package(
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    rv = packet.return_versions[-1]
    package = build_package(session, packet, rv)
    return redact_for_actor(actor, packet, package_to_dict(package))


@router.post("/filing/authorize")
def authorize_filing(
    body: AuthorizeFilingRequest,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    result = perform(
        session,
        actor,
        "authorize_filing",
        payload={"pins": body.pins},
        packet=packet,
    )
    return _redact_filing_response(actor, packet, session, result.current_state)


@router.post("/filing/{jurisdiction}/submit")
def submit_filing(
    jurisdiction: str,
    body: SubmitFilingRequest,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    _require_jurisdiction(jurisdiction)
    packet = load_packet()
    result = perform(
        session,
        actor,
        "submit_filing",
        payload={
            "jurisdiction": jurisdiction,
            "package_reference": body.package_reference,
            "status": body.status,
            "codes": body.codes,
            "submission_id": body.submission_id,
        },
        packet=packet,
    )
    return redact_for_actor(actor, packet, result.current_state)


def _reveal_pins_if_present(
    session: Session, actor: Actor, packet, entries: list[dict], entity_prefix: str
) -> None:
    """Mirrors `routes/documents.py`'s own reveal-and-log pattern: a
    cleared actor seeing a PIN gets it logged as a reveal; an uncleared
    actor's response is masked (`_redact_filing_response`) and nothing is
    logged, because nothing was revealed. Unlike `routes/documents.py`
    (which has to check *whether* a known sensitive value happens to
    appear in a page of free text), every value here is already known to
    be a PIN by construction -- there's nothing to detect, only to log."""
    if not actor.clearance:
        return
    for entry in entries:
        for _role, pin in entry.get("pins", {}).items():
            perform(
                session,
                actor,
                "reveal_sensitive_value",
                entity_id=f"{entity_prefix}:{entry['event_id']}",
                payload={"field": "efile_pin", "reason": "viewing filing status"},
                packet=packet,
            )


@router.get("/filing")
def get_filing_status(
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    authorizations = [
        {
            "event_id": str(event.id),
            "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
            "actor_id": event.actor_id,
            "package_reference": event.payload.get("package_reference"),
            "amounts_fingerprint": event.payload.get("amounts_fingerprint"),
            "identity_fingerprint": event.payload.get("identity_fingerprint"),
            "pins": event.payload.get("pins", {}),
            "simulated": event.payload.get("simulated", False),
        }
        for event in list_events_by_type(session, "filing_authorized")
    ]
    _reveal_pins_if_present(
        session, actor, packet, authorizations, "filing_authorization"
    )

    submissions = {
        jurisdiction: [
            {
                "event_id": str(event.id),
                "occurred_at": event.occurred_at.isoformat()
                if event.occurred_at
                else None,
                "status": event.payload.get("status"),
                "codes": event.payload.get("codes", []),
                "submission_id": event.payload.get("submission_id"),
                "package_reference": event.payload.get("package_reference"),
                "filed_record_id": event.payload.get("filed_record_id"),
                "simulated": event.payload.get("simulated", False),
            }
            for event in list_events_for_entity(
                session, "filing_submission", jurisdiction
            )
        ]
        for jurisdiction in _JURISDICTIONS
    }

    filed_records = [record.to_dict() for record in list_filed_records(session)]

    body = {
        "authorizations": authorizations,
        "submissions": submissions,
        "filed_records": filed_records,
    }
    return _redact_filing_response(actor, packet, session, body)


@router.get("/filing/letter-566")
def get_letter_566_pack(
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    adjustments = adjustments_by_claim(list_adjustments(session))
    body = letter_566_pack(packet, adjustments)
    return redact_for_actor(actor, packet, body)
