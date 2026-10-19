"""Bulk verify with undo (docs/UX.md S3 large detail): "if any item can't
be verified, nothing applies and the bad item is named. After applying,
an Undo toast appears; undo writes reversing events."

Verifying is a review-state marker, not a financial fact -- like
`proofline.actions.sign_offs.confirm_carryover`, it's log-only (no
expected_revision, no CAS). `bulk_verify` writes one event covering the
whole group; `undo_bulk_verify` never edits that event, it writes a new
one that names the original by id (CLAUDE.md: "Undo is a new event that
reverses an old one").
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from proofline.actions.errors import ActionValidationError, require
from proofline.actions.results import ActionResult
from proofline.analysis.calculation import line_claim_identity
from proofline.db.repository import (
    delete_claim_verification,
    get_claim_verification,
    get_event,
    insert_event,
    upsert_claim_verification,
)
from proofline.packet import Packet
from proofline.security.actors import Actor
from proofline.security.permissions import check_permission


def _lines_by_claim_key(packet: Packet, rv) -> dict[str, Any]:
    result = {}
    for line in rv.lines:
        claim = line_claim_identity(packet, line)
        if claim is not None:
            result[str(claim)] = line
    return result


def bulk_verify(
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
        raise ActionValidationError("bulk_verify needs the packet")
    check_permission(actor, "bulk_verify")
    claim_keys = require(payload, "claim_keys")
    if not isinstance(claim_keys, list) or not claim_keys:
        raise ActionValidationError("claim_keys must be a non-empty list")

    rv = packet.return_versions[-1]
    lines_by_claim = _lines_by_claim_key(packet, rv)
    for claim_key in claim_keys:
        line = lines_by_claim.get(claim_key)
        if line is None or line.value is None:
            raise ActionValidationError(
                f"{claim_key} cannot be verified: no resolvable claim with a value"
            )

    when = occurred_at or datetime.now(UTC)
    event = insert_event(
        session,
        "bulk_claims_verified",
        # `verified_role` is repeated here (also `actor.role`) so
        # `rebuild.py` can reconstruct every `ClaimVerification` row from
        # the event alone (I5) -- `Event` has no `actor_role` column.
        {"claim_keys": claim_keys, "verified_role": actor.role},
        actor_id=actor.id,
        entity_type="bulk_verify",
        entity_id=None,
        revision=None,
        occurred_at=when,
    )
    for claim_key in claim_keys:
        upsert_claim_verification(
            session,
            claim_key,
            verified_by=actor.id,
            verified_role=actor.role,
            verified_at=when,
            verified_by_event_id=str(event.id),
        )
    return ActionResult(
        event=event, current_state={"claim_keys": claim_keys, "event_id": str(event.id)}
    )


def undo_bulk_verify(
    session: Session,
    actor: Actor,
    *,
    entity_id: str | None,
    expected_revision: int | None,
    payload: dict[str, Any],
    occurred_at: datetime | None,
    packet: Packet | None = None,
) -> ActionResult:
    check_permission(actor, "undo_bulk_verify")
    raw_event_id = require(payload, "event_id")
    try:
        original_id = uuid.UUID(str(raw_event_id))
    except ValueError as exc:
        raise ActionValidationError("event_id must be a valid event id") from exc
    original = get_event(session, original_id)
    if original is None or original.event_type != "bulk_claims_verified":
        raise ActionValidationError(
            "event_id must refer to a bulk_claims_verified event"
        )

    claim_keys = original.payload["claim_keys"]
    when = occurred_at or datetime.now(UTC)
    event = insert_event(
        session,
        "bulk_claims_verification_undone",
        {"claim_keys": claim_keys, "reverses_event_id": str(original.id)},
        actor_id=actor.id,
        entity_type="bulk_verify",
        entity_id=None,
        revision=None,
        occurred_at=when,
    )
    for claim_key in claim_keys:
        # Only undo a claim's *current* verification if it's still the one
        # this event set -- if someone independently re-verified the same
        # claim in the meantime (a later `bulk_claims_verified` event),
        # that later verification is the current state and this undo must
        # leave it alone, not clobber it just because the claim key
        # happened to appear in the event being reversed.
        current = get_claim_verification(session, claim_key)
        if current is not None and current.verified_by_event_id == str(original.id):
            delete_claim_verification(session, claim_key)
    return ActionResult(
        event=event, current_state={"claim_keys": claim_keys, "event_id": str(event.id)}
    )
