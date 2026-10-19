"""The area page (S3) -- CONTRACTS.md C2/C3/C4, docs/UX.md S3. Blocking
reasons, changes since the last sign-off with carry-over confirmation,
tie-outs, grouped large detail, and one POST per C2/C4/bulk-verify action,
all through `perform()`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from proofline.actions.service import perform
from proofline.actions.sign_offs import (
    resolved_decision_ids_in_scope,
    signer_has_own_adjustment_in_scope,
)
from proofline.analysis.calculation import (
    adjustments_by_claim,
    line_claim_identity,
    workpaper_value,
)
from proofline.analysis.signoff import (
    changes_since_sign_off,
    compute_fingerprints,
    scope_lines,
)
from proofline.analysis.tie_outs import scope_tie_outs
from proofline.checks.models import Area
from proofline.db.connection import get_session
from proofline.db.repository import (
    get_claim_verification,
    get_latest_sign_off,
    list_adjustments,
    list_cases,
    record_last_seen,
)
from proofline.packet import load_packet
from proofline.security.actors import Actor
from proofline.security.dependencies import get_current_actor
from proofline.security.redact import redact_for_actor

router = APIRouter()

_AREAS: tuple[Area, ...] = (
    "identity",
    "wages",
    "investments",
    "business",
    "rentals",
    "pass_throughs",
    "deductions_credits",
    "california",
    "tax_computation",
)
_OPEN_CASE_STATUSES = {
    "open",
    "investigating",
    "waiting_on_client",
    "in_review",
    "awaiting_partner",
}


class SignOffRequest(BaseModel):
    version: str | None = None


class ConfirmCarryoverRequest(BaseModel):
    old_document_id: str
    new_document_id: str


class ConfirmDispositionRequest(BaseModel):
    expected_revision: int
    disposition: str
    reason: str | None = None


class BulkVerifyRequest(BaseModel):
    claim_keys: list[str]


class UndoBulkVerifyRequest(BaseModel):
    event_id: str


def _require_area(scope: str) -> Area:
    if scope not in _AREAS:
        raise HTTPException(status_code=404, detail=f"unknown area {scope!r}")
    return scope  # type: ignore[return-value]


def _blocking_reasons(
    session: Session, actor: Actor, packet, rv, scope: Area
) -> list[str]:
    reasons: list[str] = []
    open_cases = [
        case
        for case in list_cases(session)
        if case.scope == scope and case.status in _OPEN_CASE_STATUSES
    ]
    if open_cases:
        reasons.append(f"{len(open_cases)} open case(s) in this scope")

    previous = get_latest_sign_off(session, scope)
    if previous is not None:
        old_rv = packet.return_version(previous.engine_version)
        report = changes_since_sign_off(packet, old_rv, rv, scope)
        if report.value_changed:
            reasons.append("a value changed in this scope since the last sign-off")
        if report.scope_changed:
            reasons.append("new claims entered this scope since the last sign-off")
        resolved_decision_ids = resolved_decision_ids_in_scope(session, scope)
        current_decisions_fp = compute_fingerprints(
            rv, scope, resolved_decision_ids
        ).decisions
        if previous.decisions_fingerprint != current_decisions_fp:
            reasons.append("a decision in this scope changed since the last sign-off")
        unconfirmed = [
            old_id
            for old_id, _new_id in report.pending_documents
            if not _carryover_confirmed(session, scope, old_id)
        ]
        if unconfirmed:
            reasons.append(
                f"{len(unconfirmed)} replaced document(s) need carry-over confirmation"
            )

    adjustments = adjustments_by_claim(list_adjustments(session))
    broken = [
        tie_out
        for tie_out in scope_tie_outs(packet, rv, scope, adjustments)
        if not tie_out.ok
    ]
    if broken:
        reasons.append(f"{len(broken)} tie-out(s) do not balance")

    if signer_has_own_adjustment_in_scope(session, actor, packet, rv, scope):
        reasons.append(
            "you proposed an adjustment in this scope; another reviewer must sign"
        )
    return reasons


def _carryover_confirmed(session: Session, scope: str, old_document_id: str) -> bool:
    from proofline.db.repository import list_events_for_entity

    events = list_events_for_entity(session, "carryover", f"{scope}:{old_document_id}")
    return len(events) > 0


def _changes_payload(
    session: Session, packet, rv, scope: Area
) -> dict[str, Any] | None:
    previous = get_latest_sign_off(session, scope)
    if previous is None:
        return None
    old_rv = packet.return_version(previous.engine_version)
    report = changes_since_sign_off(packet, old_rv, rv, scope)
    documents = []
    for old_id, new_id in report.pending_documents:
        comparison = report.document_comparisons.get((old_id, new_id))
        documents.append(
            {
                "old_document_id": old_id,
                "new_document_id": new_id,
                "confirmed": _carryover_confirmed(session, scope, old_id),
                "unchanged_count": len(comparison.unchanged) if comparison else 0,
                "changed_count": len(comparison.changed) if comparison else 0,
                "changed": [
                    {
                        "claim_key": c.comparison_key,
                        "old_value": c.old_value,
                        "new_value": c.new_value,
                    }
                    for c in (comparison.changed if comparison else ())
                ],
            }
        )
    resolved_decision_ids = resolved_decision_ids_in_scope(session, scope)
    current_decisions_fp = compute_fingerprints(
        rv, scope, resolved_decision_ids
    ).decisions
    return {
        "since_version": previous.version,
        "value_changed": report.value_changed,
        "evidence_only_changed": report.evidence_only_changed,
        "scope_changed": report.scope_changed,
        "decision_changed": previous.decisions_fingerprint != current_decisions_fp,
        "documents": documents,
    }


def _detail_rows(session: Session, packet, rv, scope: Area, adjustments) -> list[dict]:
    rows = []
    for line in scope_lines(rv, scope):
        claim = line_claim_identity(packet, line)
        claim_key = str(claim) if claim is not None else None
        verification = get_claim_verification(session, claim_key) if claim_key else None
        workpaper = workpaper_value(packet, rv, line.key, adjustments)
        rows.append(
            {
                "line_key": line.key,
                "label": line.label,
                "claim_key": claim_key,
                "value": workpaper.value,
                "provenance_label": workpaper.label,
                "verified": verification is not None,
                "verified_by": verification.verified_by if verification else None,
            }
        )
    return rows


@router.get("/areas/{scope}")
def get_area(
    scope: str,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    area = _require_area(scope)
    packet = load_packet()
    rv = packet.return_versions[-1]
    record_last_seen(session, actor.id, "area", area, datetime.now(UTC))

    latest_sign_off = get_latest_sign_off(session, area)
    adjustments = adjustments_by_claim(list_adjustments(session))
    active_adjustments_in_scope = [
        a
        for a in list_adjustments(session)
        if a.claim_key
        in {
            str(claim)
            for line in scope_lines(rv, area)
            if (claim := line_claim_identity(packet, line)) is not None
        }
    ]
    body = {
        "scope": area,
        "sign_off": latest_sign_off.to_dict() if latest_sign_off else None,
        "active_adjustments_count": len(active_adjustments_in_scope),
        "blocking_reasons": _blocking_reasons(session, actor, packet, rv, area),
        "changes_since_sign_off": _changes_payload(session, packet, rv, area),
        "tie_outs": [
            {
                "line_key": t.line_key,
                "label": t.label,
                "engine_value": t.engine_value,
                "workpaper_value": t.workpaper_value,
                "ok": t.ok,
                "difference": t.difference,
            }
            for t in scope_tie_outs(packet, rv, area, adjustments)
        ],
        "detail": _detail_rows(session, packet, rv, area, adjustments),
    }
    return redact_for_actor(actor, packet, body)


@router.post("/areas/{scope}/sign-off")
def sign_off(
    scope: str,
    body: SignOffRequest,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    area = _require_area(scope)
    packet = load_packet()
    payload: dict[str, Any] = {"scope": area}
    if body.version is not None:
        payload["version"] = body.version
    result = perform(session, actor, "sign_off", payload=payload, packet=packet)
    return redact_for_actor(actor, packet, result.current_state.to_dict())


@router.post("/areas/{scope}/confirm-carryover")
def confirm_carryover(
    scope: str,
    body: ConfirmCarryoverRequest,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    area = _require_area(scope)
    packet = load_packet()
    result = perform(
        session,
        actor,
        "confirm_carryover",
        payload={
            "scope": area,
            "old_document_id": body.old_document_id,
            "new_document_id": body.new_document_id,
        },
        packet=packet,
    )
    return redact_for_actor(
        actor, packet, {"confirmed": True, "event_id": str(result.event.id)}
    )


@router.post("/documents/{document_id}/confirm-disposition")
def confirm_disposition(
    document_id: str,
    body: ConfirmDispositionRequest,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    result = perform(
        session,
        actor,
        "confirm_disposition",
        entity_id=document_id,
        expected_revision=body.expected_revision,
        payload={"disposition": body.disposition, "reason": body.reason},
        packet=packet,
    )
    return redact_for_actor(actor, packet, result.current_state.to_dict())


@router.post("/areas/{scope}/bulk-verify")
def bulk_verify(
    scope: str,
    body: BulkVerifyRequest,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    _require_area(scope)
    packet = load_packet()
    result = perform(
        session,
        actor,
        "bulk_verify",
        payload={"claim_keys": body.claim_keys},
        packet=packet,
    )
    return redact_for_actor(actor, packet, result.current_state)


@router.post("/areas/{scope}/undo-bulk-verify")
def undo_bulk_verify(
    scope: str,
    body: UndoBulkVerifyRequest,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    _require_area(scope)
    packet = load_packet()
    result = perform(
        session,
        actor,
        "undo_bulk_verify",
        payload={"event_id": body.event_id},
        packet=packet,
    )
    return redact_for_actor(actor, packet, result.current_state)
