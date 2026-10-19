"""The one entry point every write goes through:
`perform(session, actor, action, ...)`.

Permission, validation, the current-state compare-and-set and the event
write all happen against the one `session` the caller supplies and is
responsible for committing -- `proofline.db.connection.get_session` commits
at the end of a request only if nothing raised, and rolls back the whole
thing otherwise, so a failure here writes neither the event nor the
current state (CONTRACTS.md Storage, acceptance test I1).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from proofline.actions import (
    bulk,
    cases,
    check_runs,
    disposition,
    filing,
    readiness,
    reveal,
    review_notes,
    sign_offs,
)
from proofline.actions.results import ActionResult
from proofline.packet import Packet
from proofline.security.actors import Actor

_HANDLERS = {
    "add_review_note": review_notes.add_review_note,
    "respond_review_note": review_notes.respond_review_note,
    "resolve_review_note": review_notes.resolve_review_note,
    "reveal_sensitive_value": reveal.reveal_sensitive_value,
    "record_check_run": check_runs.record_check_run,
    "open_case_by_hand": cases.open_case_by_hand,
    "sync_cases": cases.sync_cases,
    "pick_up": cases.pick_up,
    "ask_client": cases.ask_client,
    "client_answered": cases.client_answered,
    "submit_proposal": cases.submit_proposal,
    "return": cases.return_proposal,
    "approve": cases.approve,
    "partner_approve": cases.partner_approve,
    "partner_return": cases.partner_return,
    "reopen": cases.reopen,
    "reassign": cases.reassign,
    "sign_off": sign_offs.sign_off,
    "confirm_carryover": sign_offs.confirm_carryover,
    "confirm_disposition": disposition.confirm_disposition,
    "bulk_verify": bulk.bulk_verify,
    "undo_bulk_verify": bulk.undo_bulk_verify,
    "confirm_readiness_item": readiness.confirm_readiness_item,
    "authorize_filing": filing.authorize_filing,
    "submit_filing": filing.submit_filing,
}


def perform(
    session: Session,
    actor: Actor,
    action: str,
    *,
    entity_id: str | None = None,
    expected_revision: int | None = None,
    payload: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
    packet: Packet | None = None,
) -> ActionResult:
    try:
        handler = _HANDLERS[action]
    except KeyError:
        raise ValueError(f"unknown action {action!r}") from None
    return handler(
        session,
        actor,
        entity_id=entity_id,
        expected_revision=expected_revision,
        payload=payload or {},
        occurred_at=occurred_at,
        packet=packet,
    )
