"""Replays every event, in `seq` order, into fresh current-state tables.

Migrations change the shape of tables; this replays the facts back into
them. Rebuilding after a migration must give exactly the state that was
already stored (CONTRACTS.md Storage, acceptance test I5) -- this module is
also how that gets checked, by comparing its output against the live
tables `proofline.actions.service.perform` built one action at a time.

Each event type is replayed by a handler keyed on `(event_type,
schema_version)`, so a future change to an event's payload shape can add a
new handler for the new `schema_version` without breaking how an old event
is read (CONTRACTS.md: "`rebuild.py` knows how to read the old versions, so
old events stay valid forever"). An event with no matching handler --
Step 1's throwaway "test_event" rows, or a log-only event type that has no
current-state row at all (`sensitive_value_revealed`) -- is read and
skipped, not an error.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeAlias

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from proofline.db.models import (
    Adjustment,
    Case,
    CaseDecision,
    CaseProposal,
    CheckRun,
    ClaimVerification,
    DocumentDisposition,
    Event,
    FiledRecord,
    ReviewNote,
    SignOff,
)

_Handler: TypeAlias = Callable[[Session, Event], None]
_HANDLERS: dict[tuple[str, int], _Handler] = {}


def _register(
    event_type: str, schema_version: int = 1
) -> Callable[[_Handler], _Handler]:
    def decorator(handler: _Handler) -> _Handler:
        _HANDLERS[(event_type, schema_version)] = handler
        return handler

    return decorator


@_register("review_note_added")
def _replay_review_note_added(session: Session, event: Event) -> None:
    session.add(
        ReviewNote(
            id=event.entity_id,
            about_type=event.payload["about_type"],
            about_id=event.payload["about_id"],
            opened_by=event.actor_id,
            opened_at=event.occurred_at,
            status="open",
            revision=event.revision,
            body=event.payload.get("body"),
        )
    )


@_register("review_note_responded")
def _replay_review_note_responded(session: Session, event: Event) -> None:
    note = session.get(ReviewNote, event.entity_id)
    if note is not None:
        note.revision = event.revision
        note.body = event.payload.get("body")


@_register("review_note_resolved")
def _replay_review_note_resolved(session: Session, event: Event) -> None:
    note = session.get(ReviewNote, event.entity_id)
    if note is not None:
        note.status = "resolved"
        note.resolved_by = event.actor_id
        note.resolved_at = event.occurred_at
        note.resolution = event.payload.get("resolution")
        note.revision = event.revision


@_register("check_run_recorded")
def _replay_check_run_recorded(session: Session, event: Event) -> None:
    session.add(
        CheckRun(
            id=event.entity_id,
            event_id=event.id,
            return_version=event.payload["return_version"],
            findings=event.payload["findings"],
            failures=event.payload["failures"],
        )
    )


@_register("case_opened")
def _replay_case_opened(session: Session, event: Event) -> None:
    payload = event.payload
    if payload.get("origin") == "check":
        # `case_opened` for a check-origin case carries the full finding so
        # the case row can be rebuilt without rerunning the check that
        # produced it (the check's logic can change later; the event must
        # stay replayable, CONTRACTS.md Storage).
        from proofline.actions.cases import _case_from_finding
        from proofline.checks.models import CheckResult

        finding = CheckResult.model_validate(payload["finding"])
        case = _case_from_finding(event.entity_id, finding)
        case.revision = event.revision
        session.add(case)
        return
    session.add(
        Case(
            case_id=event.entity_id,
            root_cause_key=payload["root_cause_key"],
            origin=payload["origin"],
            origin_ref=payload.get("origin_ref"),
            scope=payload["scope"],
            claims=payload.get("claims", []),
            severity=payload["severity"],
            finding_type=None,
            status="open",
            revision=event.revision,
            evidence_refs=payload.get("evidence_refs", []),
            observed=payload["observed"],
            expected=payload["expected"],
            limitations=payload.get("limitations"),
            recommended_action=payload.get("recommended_action"),
            assignee_id=payload.get("assignee_id"),
            impact_unknown=bool(payload.get("impact_unknown", True)),
        )
    )


@_register("case_cleared")
def _replay_case_cleared(session: Session, event: Event) -> None:
    case = session.get(Case, event.entity_id)
    if case is not None:
        case.status = "cleared"
        case.cleared_reason = event.payload.get("reason")
        case.revision = event.revision


@_register("case_picked_up")
def _replay_case_picked_up(session: Session, event: Event) -> None:
    case = session.get(Case, event.entity_id)
    if case is not None:
        case.status = "investigating"
        case.assignee_id = event.actor_id
        case.revision = event.revision


@_register("case_client_asked")
def _replay_case_client_asked(session: Session, event: Event) -> None:
    case = session.get(Case, event.entity_id)
    if case is not None:
        case.status = "waiting_on_client"
        case.revision = event.revision


@_register("case_client_answered")
def _replay_case_client_answered(session: Session, event: Event) -> None:
    case = session.get(Case, event.entity_id)
    if case is not None:
        case.status = "investigating"
        case.evidence_refs = [*case.evidence_refs, event.payload["evidence_ref"]]
        case.revision = event.revision


@_register("case_proposal_submitted")
def _replay_case_proposal_submitted(session: Session, event: Event) -> None:
    payload = event.payload
    session.add(
        CaseProposal(
            id=payload["proposal_id"],
            case_id=event.entity_id,
            revision_number=payload["revision_number"],
            resolution_type=payload["resolution_type"],
            fields=payload.get("fields", {}),
            evidence_refs=payload.get("evidence_refs", []),
            proposed_by=event.actor_id,
            proposed_at=event.occurred_at,
        )
    )
    case = session.get(Case, event.entity_id)
    if case is not None:
        case.status = "in_review"
        case.revision = event.revision


def _replay_decision(
    session: Session, event: Event, decision: str, new_status: str
) -> None:
    payload = event.payload
    session.add(
        CaseDecision(
            id=payload["decision_id"],
            case_id=event.entity_id,
            proposal_revision=payload.get("proposal_revision"),
            decision=decision,
            decided_by=event.actor_id,
            decided_at=event.occurred_at,
            note=payload.get("note"),
        )
    )
    case = session.get(Case, event.entity_id)
    if case is not None:
        case.status = new_status
        case.revision = event.revision

    adjustment_ids = payload.get("adjustment_ids")
    if not adjustment_ids:
        return
    proposal = session.scalars(
        select(CaseProposal).where(
            CaseProposal.case_id == event.entity_id,
            CaseProposal.revision_number == payload.get("proposal_revision"),
        )
    ).one_or_none()
    if proposal is None:
        return
    for adjustment_id, entry in zip(
        adjustment_ids, proposal.fields.get("adjustments", []), strict=True
    ):
        session.add(
            Adjustment(
                id=adjustment_id,
                claim_key=str(entry["claim"]),
                old_value=str(entry["old_value"]),
                new_value=str(entry["new_value"]),
                evidence_refs=proposal.evidence_refs,
                case_id=event.entity_id,
                decision_id=payload["decision_id"],
                created_at=event.occurred_at,
            )
        )


@_register("case_returned")
def _replay_case_returned(session: Session, event: Event) -> None:
    _replay_decision(session, event, "return", "investigating")


@_register("case_approved")
def _replay_case_approved(session: Session, event: Event) -> None:
    _replay_decision(session, event, "approve", event.payload["next_status"])


@_register("case_partner_approved")
def _replay_case_partner_approved(session: Session, event: Event) -> None:
    _replay_decision(session, event, "partner_approve", "resolved")


@_register("case_partner_returned")
def _replay_case_partner_returned(session: Session, event: Event) -> None:
    _replay_decision(session, event, "partner_return", "investigating")


@_register("case_reopened")
def _replay_case_reopened(session: Session, event: Event) -> None:
    case = session.get(Case, event.entity_id)
    if case is not None:
        case.status = "investigating"
        case.revision = event.revision


@_register("case_reassigned")
def _replay_case_reassigned(session: Session, event: Event) -> None:
    case = session.get(Case, event.entity_id)
    if case is not None:
        case.assignee_id = event.payload["assignee_id"]
        case.revision = event.revision


@_register("sign_off_recorded")
def _replay_sign_off_recorded(session: Session, event: Event) -> None:
    payload = event.payload
    session.add(
        SignOff(
            id=event.entity_id,
            scope=payload["scope"],
            version=payload["version"],
            signed_by=event.actor_id,
            signed_role=payload["signed_role"],
            signed_at=event.occurred_at,
            engine_version=payload["engine_version"],
            active_adjustment_ids=payload.get("active_adjustment_ids", []),
            evidence_fingerprint=payload["evidence_fingerprint"],
            values_fingerprint=payload["values_fingerprint"],
            decisions_fingerprint=payload["decisions_fingerprint"],
            scope_fingerprint=payload["scope_fingerprint"],
        )
    )


@_register("document_disposition_confirmed")
def _replay_document_disposition_confirmed(session: Session, event: Event) -> None:
    payload = event.payload
    existing = session.get(DocumentDisposition, event.entity_id)
    if existing is None:
        session.add(
            DocumentDisposition(
                document_id=event.entity_id,
                disposition=payload["disposition"],
                reason=payload.get("reason"),
                confirmed_by=event.actor_id,
                confirmed_at=event.occurred_at,
                revision=event.revision,
            )
        )
        return
    existing.disposition = payload["disposition"]
    existing.reason = payload.get("reason")
    existing.confirmed_by = event.actor_id
    existing.confirmed_at = event.occurred_at
    existing.revision = event.revision


@_register("bulk_claims_verified")
def _replay_bulk_claims_verified(session: Session, event: Event) -> None:
    payload = event.payload
    for claim_key in payload["claim_keys"]:
        existing = session.get(ClaimVerification, claim_key)
        if existing is None:
            session.add(
                ClaimVerification(
                    claim_key=claim_key,
                    verified_by=event.actor_id,
                    verified_role=payload["verified_role"],
                    verified_at=event.occurred_at,
                    verified_by_event_id=str(event.id),
                )
            )
            continue
        existing.verified_by = event.actor_id
        existing.verified_role = payload["verified_role"]
        existing.verified_at = event.occurred_at
        existing.verified_by_event_id = str(event.id)


@_register("bulk_claims_verification_undone")
def _replay_bulk_claims_verification_undone(session: Session, event: Event) -> None:
    for claim_key in event.payload["claim_keys"]:
        existing = session.get(ClaimVerification, claim_key)
        if existing is not None:
            session.delete(existing)


@_register("filing_submitted")
def _replay_filing_submitted(session: Session, event: Event) -> None:
    """Only an accepted submission leaves a current-state row (I6: the
    filed record is written once, on acceptance, never on rejection) --
    `filed_record_id` is only present in the payload for that case, same
    reason `case_opened` carries the full finding: the row's own id must
    come from the event, not be invented again at replay time."""
    payload = event.payload
    filed_record_id = payload.get("filed_record_id")
    if filed_record_id is None:
        return
    session.add(
        FiledRecord(
            id=filed_record_id,
            jurisdiction=payload["jurisdiction"],
            package_reference=payload["package_reference"],
            amounts_fingerprint=payload["amounts_fingerprint"],
            identity_fingerprint=payload["identity_fingerprint"],
            accepted_at=event.occurred_at,
            submission_event_id=event.id,
            amends_filed_record_id=payload.get("amends_filed_record_id"),
        )
    )


def rebuild_current_state(session: Session) -> None:
    """Clears every current-state table this module knows how to rebuild,
    then replays the full event history back into them, in `seq` order."""
    session.execute(delete(ReviewNote))
    session.execute(delete(ClaimVerification))
    session.execute(delete(SignOff))
    session.execute(delete(CheckRun))
    session.execute(delete(DocumentDisposition))
    session.execute(delete(Adjustment))
    session.execute(delete(CaseDecision))
    session.execute(delete(CaseProposal))
    session.execute(delete(Case))
    session.execute(delete(FiledRecord))
    session.flush()
    for event in session.scalars(select(Event).order_by(Event.seq)):
        handler = _HANDLERS.get((event.event_type, event.schema_version))
        if handler is not None:
            handler(session, event)
    session.flush()
