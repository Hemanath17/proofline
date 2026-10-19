"""C2 sign-off actions: `sign_off` and `confirm_carryover`.

Sign-offs are append-only -- a new version is always a new `SignOff` row,
never an update to the last one (CONTRACTS.md: "version n+1 is version n
plus that change. Both are kept"). `confirm_carryover` is log-only, like
`reveal_sensitive_value`: there's nothing to version, so it writes only an
event, which doubles as the record that a replaced document's carry-over
was confirmed (CONTRACTS.md: "The reviewer confirms each replaced document
once").
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from proofline.actions.errors import ActionConflict, ActionValidationError, require
from proofline.actions.results import ActionResult
from proofline.analysis.calculation import line_claim_identity
from proofline.analysis.signoff import (
    changes_since_sign_off,
    compute_fingerprints,
    scope_lines,
)
from proofline.db.models import SignOff
from proofline.db.repository import (
    get_latest_sign_off,
    insert_event,
    insert_sign_off,
    list_adjustments,
    list_case_decisions,
    list_case_proposals,
    list_cases,
    list_events_for_entity,
)
from proofline.packet import Packet
from proofline.security.actors import Actor
from proofline.security.permissions import check_permission

_REVIEWER_ROLES = frozenset({"reviewer", "quality_reviewer"})


def _carryover_confirmed(session: Session, scope: str, old_document_id: str) -> bool:
    events = list_events_for_entity(session, "carryover", f"{scope}:{old_document_id}")
    return len(events) > 0


def resolved_decision_ids_in_scope(session: Session, scope: str) -> list[str]:
    """CONTRACTS.md C2's "decisions" fingerprint: "resolved cases and
    judgments in the scope, with the revision approved." A case already
    carries its own scope (set at open time, same grouping C2 itself
    uses), so every `approve`/`partner_approve` decision on a case in
    this scope counts -- `return`/`partner_return` don't, since those
    don't resolve anything."""
    decision_ids: list[str] = []
    for case in list_cases(session):
        if case.scope != scope:
            continue
        for decision in list_case_decisions(session, case.case_id):
            if decision.decision in ("approve", "partner_approve"):
                decision_ids.append(decision.id)
    return decision_ids


def signer_has_own_adjustment_in_scope(
    session: Session, actor: Actor, packet: Packet, rv, scope: str
) -> bool:
    """CONTRACTS.md C2: "Nobody signs a scope that contains their own
    adjustment." An adjustment's claim is in scope if any of the scope's
    current lines resolve to that claim; the adjustment's own proposer is
    read off the case it came from."""
    claim_keys_in_scope = {
        str(claim)
        for line in scope_lines(rv, scope)
        if (claim := line_claim_identity(packet, line)) is not None
    }
    if not claim_keys_in_scope:
        return False
    cases_by_id = {case.case_id: case for case in list_cases(session)}
    for adjustment in list_adjustments(session):
        if (
            adjustment.claim_key not in claim_keys_in_scope
            or adjustment.case_id is None
        ):
            continue
        case = cases_by_id.get(adjustment.case_id)
        if case is None:
            continue
        proposals = list_case_proposals(session, case.case_id)
        if any(proposal.proposed_by == actor.id for proposal in proposals):
            return True
    return False


def sign_off(
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
        raise ActionValidationError("sign_off needs the packet")
    scope = require(payload, "scope")
    check_permission(actor, "sign_off", scope=scope)

    # Which engine version to sign at -- defaults to the latest, but a
    # caller can sign an earlier one explicitly (CONTRACTS.md A2: Investments
    # is first signed "at v1", then re-signed once D31/v2 arrives). Every
    # return version co-exists in the packet from the start (engine
    # versions never change), so there's no "current" version without
    # this -- `sign_off` can't otherwise reproduce a scope's progression
    # across versions.
    version = payload.get("version") or packet.return_versions[-1].version
    rv = packet.return_version(version)
    if signer_has_own_adjustment_in_scope(session, actor, packet, rv, scope):
        raise ActionConflict(
            "nobody signs a scope that contains their own adjustment", current=None
        )

    previous = get_latest_sign_off(session, scope)
    if previous is not None:
        old_rv = packet.return_version(previous.engine_version)
        report = changes_since_sign_off(packet, old_rv, rv, scope)
        # A value change does *not* block signing again -- calling
        # sign_off a second time, at the new version, is itself "the
        # reviewer approves the change" (CONTRACTS.md C2: "Version n+1 is
        # version n plus that change. Both are kept"). What a value
        # change *does* mean is shown as "signed, change pending" on the
        # area page (`routes/areas.py`) until this call happens -- a
        # display status computed from `changes_since_sign_off`, not a
        # gate inside the action. Only a document replacement still
        # blocks here: CONTRACTS.md requires one `confirm_carryover` per
        # replaced document before the scope can be signed again,
        # regardless of whether that replacement's dependents also
        # changed value.
        for old_id, _new_id in report.pending_documents:
            if not _carryover_confirmed(session, scope, old_id):
                raise ActionConflict(
                    f"confirm the carry-over for replaced document {old_id} first",
                    current=previous.to_dict(),
                )

    resolved_decision_ids = resolved_decision_ids_in_scope(session, scope)
    fingerprints = compute_fingerprints(rv, scope, resolved_decision_ids)
    when = occurred_at or datetime.now(UTC)
    sign_off_id = f"signoff-{uuid.uuid4()}"
    row = SignOff(
        id=sign_off_id,
        scope=scope,
        version=(previous.version + 1 if previous is not None else 1),
        signed_by=actor.id,
        signed_role=actor.role,
        signed_at=when,
        engine_version=rv.version,
        active_adjustment_ids=[a.id for a in list_adjustments(session)],
        evidence_fingerprint=fingerprints.evidence,
        values_fingerprint=fingerprints.values,
        decisions_fingerprint=fingerprints.decisions,
        scope_fingerprint=fingerprints.scope,
    )
    try:
        insert_sign_off(session, row)
    except IntegrityError:
        # Two reviewers racing to sign the same scope both read the same
        # `previous.version` and both tried to insert the same next
        # version -- `sign_offs`'s own (scope, version) unique index
        # catches the second one at the database level (acceptance test
        # I2's spirit, same as a stale-revision race, even though
        # sign-offs have no `expected_revision` of their own to be stale).
        # Roll back this action's own not-yet-committed insert (nothing
        # else was written before it, so this satisfies I1: "a failed one
        # writes neither"), then report whoever actually won as `current`
        # -- captured as a dict while the session is still open, same
        # reason `StaleRevision`/`ActionConflict` elsewhere never carry
        # the ORM row itself (it would raise `DetachedInstanceError` once
        # this request's session closes).
        session.rollback()
        current = get_latest_sign_off(session, scope)
        raise ActionConflict(
            "this scope was already signed at that version; refresh and try again",
            current=current.to_dict() if current is not None else None,
        ) from None
    event = insert_event(
        session,
        "sign_off_recorded",
        {
            # Everything `rebuild.py` needs to reconstruct this `SignOff`
            # row from the event alone (I5) -- `signed_by`/`signed_at` are
            # also on the event itself (actor_id/occurred_at), but are
            # repeated here so the handler reads one place, not two.
            "scope": scope,
            "version": row.version,
            "signed_role": actor.role,
            "engine_version": rv.version,
            "active_adjustment_ids": row.active_adjustment_ids,
            "evidence_fingerprint": fingerprints.evidence,
            "values_fingerprint": fingerprints.values,
            "decisions_fingerprint": fingerprints.decisions,
            "scope_fingerprint": fingerprints.scope,
        },
        actor_id=actor.id,
        entity_type="sign_off",
        entity_id=sign_off_id,
        revision=None,
        occurred_at=when,
    )
    return ActionResult(event=event, current_state=row)


def confirm_carryover(
    session: Session,
    actor: Actor,
    *,
    entity_id: str | None,
    expected_revision: int | None,
    payload: dict[str, Any],
    occurred_at: datetime | None,
    packet: Packet | None = None,
) -> ActionResult:
    check_permission(actor, "confirm_carryover")
    if packet is None:
        raise ActionValidationError("confirm_carryover needs the packet")
    scope = require(payload, "scope")
    old_document_id = require(payload, "old_document_id")
    new_document_id = require(payload, "new_document_id")

    # Confirming a carry-over is a safety-relevant claim ("this document
    # swap is eligible to carry the old sign-off forward") -- it must be
    # about a real, resolver-found replacement in this scope, not
    # whatever (old_document_id, new_document_id) pair a caller happens
    # to send. Reusing `changes_since_sign_off`'s own scoped
    # `pending_documents` means this can never drift from what
    # `sign_off`'s own blocking check (`_carryover_confirmed`) considers
    # pending.
    previous = get_latest_sign_off(session, scope)
    if previous is None:
        raise ActionValidationError(
            f"{scope} has never been signed off; there is nothing to carry over"
        )
    old_rv = packet.return_version(previous.engine_version)
    rv = packet.return_versions[-1]
    pending = dict(changes_since_sign_off(packet, old_rv, rv, scope).pending_documents)
    if old_document_id not in pending:
        raise ActionValidationError(
            f"{old_document_id} is not a pending document replacement in scope {scope!r}"
        )
    if pending[old_document_id] != new_document_id:
        raise ActionValidationError(
            f"{old_document_id} was replaced by {pending[old_document_id]!r}, "
            f"not {new_document_id!r}"
        )

    when = occurred_at or datetime.now(UTC)
    event = insert_event(
        session,
        "carryover_confirmed",
        {"scope": scope, "new_document_id": new_document_id},
        actor_id=actor.id,
        entity_type="carryover",
        entity_id=f"{scope}:{old_document_id}",
        revision=None,
        occurred_at=when,
    )
    return ActionResult(event=event, current_state=None)
