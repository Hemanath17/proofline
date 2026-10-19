"""C5's package authorization and submission (CONTRACTS.md C5, acceptance
test A3). Both are replays, labelled "Simulated" per CLAUDE.md: the real
e-file transmitter and the taxpayer's own pen are outside this system, so
these actions record what the packet's own timeline says happened --
`authorize_filing` is the Form 8879/FTB 8879 signature event (`tl-20`),
and `submit_filing` records a submission's actual result (status and any
codes), which the caller supplies the same way a replay supplies a date:
as history being re-entered, not something this system transmits for
real.

Resolved, per CLAUDE.md and A3: correcting the taxpayer's SSN, name or
address always needs a new signature, no threshold -- and so does an
amounts-only change (CONTRACTS.md's "even $2 is $2" already said so).
Since `package_reference` is a hash over everything in the package,
`submit_filing` enforcing "the package being submitted is exactly the
one most recently authorized" is the one general rule that covers both:
any change to either fingerprint changes the reference, which changes
what must be (re-)authorized first.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from proofline.actions.errors import ActionConflict, ActionValidationError, require
from proofline.actions.results import ActionResult
from proofline.analysis.filing import build_package
from proofline.db.models import FiledRecord
from proofline.db.repository import (
    get_latest_filed_record,
    insert_event,
    insert_filed_record,
    list_events_by_type,
)
from proofline.packet import Packet
from proofline.security.actors import Actor
from proofline.security.permissions import check_permission

_SIGNING_ROLES = frozenset({"taxpayer", "spouse"})
_JURISDICTIONS = frozenset({"federal", "california"})
_STATUSES = frozenset({"accepted", "rejected", "not_transmitted"})


def authorize_filing(
    session: Session,
    actor: Actor,
    *,
    entity_id: str | None,
    expected_revision: int | None,
    payload: dict[str, Any],
    occurred_at: datetime | None,
    packet: Packet | None = None,
) -> ActionResult:
    if packet is None:
        raise ActionValidationError("authorize_filing needs the packet")
    check_permission(actor, "authorize_filing")

    pins = payload.get("pins")
    if not isinstance(pins, dict) or not pins:
        raise ActionValidationError(
            "pins (a mapping of signer role to PIN) is required"
        )
    expected_roles = {
        person.role
        for person in packet.household.people
        if person.role in _SIGNING_ROLES
    }
    if set(pins) != expected_roles:
        raise ActionValidationError(f"pins must cover exactly {sorted(expected_roles)}")
    for role, pin in pins.items():
        if not isinstance(pin, str) or not pin.strip():
            raise ActionValidationError(f"pin for {role!r} is required")

    rv = packet.return_versions[-1]
    package = build_package(session, packet, rv)
    when = occurred_at or datetime.now(UTC)
    event = insert_event(
        session,
        "filing_authorized",
        {
            "package_reference": package.reference,
            "amounts_fingerprint": package.amounts_fingerprint,
            "identity_fingerprint": package.identity_fingerprint,
            "pins": pins,
            "simulated": True,
        },
        actor_id=actor.id,
        entity_type="filing_authorization",
        entity_id=package.reference,
        revision=None,
        occurred_at=when,
    )
    return ActionResult(
        event=event,
        current_state={
            "package_reference": package.reference,
            "amounts_fingerprint": package.amounts_fingerprint,
            "identity_fingerprint": package.identity_fingerprint,
            "pins": pins,
            "simulated": True,
            "event_id": str(event.id),
        },
    )


def _latest_authorization(session: Session) -> dict[str, Any] | None:
    events = list_events_by_type(session, "filing_authorized")
    return events[-1].payload if events else None


def submit_filing(
    session: Session,
    actor: Actor,
    *,
    entity_id: str | None,
    expected_revision: int | None,
    payload: dict[str, Any],
    occurred_at: datetime | None,
    packet: Packet | None = None,
) -> ActionResult:
    check_permission(actor, "submit_filing")
    jurisdiction = require(payload, "jurisdiction")
    if jurisdiction not in _JURISDICTIONS:
        raise ActionValidationError(
            f"jurisdiction must be one of {sorted(_JURISDICTIONS)}"
        )
    package_reference = require(payload, "package_reference")
    status = require(payload, "status")
    if status not in _STATUSES:
        raise ActionValidationError(f"status must be one of {sorted(_STATUSES)}")
    codes = payload.get("codes", [])
    submission_id = payload.get("submission_id")

    authorization = _latest_authorization(session)
    if authorization is None:
        raise ActionValidationError(
            "this package has never been authorized -- call authorize_filing first"
        )
    if authorization["package_reference"] != package_reference:
        raise ActionConflict(
            "the authorized package has changed since this reference was captured "
            "-- authorize_filing again before submitting",
            current={"package_reference": authorization["package_reference"]},
        )
    if (
        status == "accepted"
        and get_latest_filed_record(session, jurisdiction) is not None
    ):
        # CONTRACTS.md I6: "written once, when the return is accepted."
        # Amendments (a new package pointing at the filed record it
        # amends) are Step 9+ work -- until that exists, a jurisdiction
        # that already has a filed record has nothing left to accept.
        raise ActionConflict(
            f"{jurisdiction} already has a filed record; amendments aren't built yet",
            current=None,
        )

    when = occurred_at or datetime.now(UTC)
    filed_record_id = None
    event_payload: dict[str, Any] = {
        "jurisdiction": jurisdiction,
        "package_reference": package_reference,
        "amounts_fingerprint": authorization["amounts_fingerprint"],
        "identity_fingerprint": authorization["identity_fingerprint"],
        "status": status,
        "codes": codes,
        "submission_id": submission_id,
        "simulated": True,
    }
    if status == "accepted":
        filed_record_id = f"filed-{uuid.uuid4()}"
        event_payload["filed_record_id"] = filed_record_id

    event = insert_event(
        session,
        "filing_submitted",
        event_payload,
        actor_id=actor.id,
        entity_type="filing_submission",
        entity_id=jurisdiction,
        revision=None,
        occurred_at=when,
    )

    if filed_record_id is not None:
        try:
            insert_filed_record(
                session,
                FiledRecord(
                    id=filed_record_id,
                    jurisdiction=jurisdiction,
                    package_reference=package_reference,
                    amounts_fingerprint=authorization["amounts_fingerprint"],
                    identity_fingerprint=authorization["identity_fingerprint"],
                    accepted_at=when,
                    submission_event_id=event.id,
                    amends_filed_record_id=None,
                ),
            )
        except IntegrityError:
            # Two accept calls for the same jurisdiction raced past the
            # `get_latest_filed_record` check above before either
            # committed -- `filed_records`'s own unique index on
            # `jurisdiction` catches the second one here, the same race
            # class (and the same fix shape) as `sign_offs`'s
            # (scope, version) index. Rolling back discards this
            # transaction's own not-yet-committed event too (I1: "a
            # failed one writes neither").
            session.rollback()
            current = get_latest_filed_record(session, jurisdiction)
            raise ActionConflict(
                f"{jurisdiction} already has a filed record; amendments aren't "
                "built yet",
                current=current.to_dict() if current is not None else None,
            ) from None

    return ActionResult(
        event=event,
        current_state={
            "jurisdiction": jurisdiction,
            "status": status,
            "codes": codes,
            "filed_record_id": filed_record_id,
            "event_id": str(event.id),
        },
    )
