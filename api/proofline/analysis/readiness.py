"""C5: are we ready to file.

Eight items read straight off state that already exists -- no new action,
just the same logic the area page (`routes/areas.py`) and Step 7's
sign-off code already compute, reused rather than re-decided. Four more
are a plain attestation (`proofline.actions.readiness.confirm_readiness_item`):
nothing in the packet can derive "identity verified" or "due diligence
done," so a staff member records each once, and its state is read back by
replaying its own events, same as any other log-only action
(`proofline.actions.sign_offs.confirm_carryover`).

Every item carries a named reason when it isn't met (docs/UX.md's "what
blocks" pattern) -- filing is blocked while any item is unmet.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from proofline.analysis.signoff import (
    changes_since_sign_off,
    compute_fingerprints,
    resolved_decision_ids_in_scope,
)
from proofline.checks.models import Area
from proofline.checks.money import parse_money
from proofline.db.models import Event
from proofline.db.repository import (
    get_document_disposition,
    get_latest_sign_off,
    list_cases,
    list_events_for_entity,
    list_review_notes,
)
from proofline.packet import Packet

AREAS: tuple[Area, ...] = (
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

ATTESTATION_ITEMS: dict[str, str] = {
    "identity_verified": "Identity verified",
    "prior_year_return_reviewed": "Prior-year return reviewed",
    "prior_year_variances_explained": "Prior-year variances explained",
    "due_diligence_done": "Due diligence done",
}


@dataclass(frozen=True)
class ReadinessItem:
    item: str
    label: str
    kind: str  # "derived" | "attestation"
    met: bool
    reasons: list[str]
    confirmed_by: str | None = None
    confirmed_at: str | None = None
    note: str | None = None


def _carryover_confirmed(session: Session, scope: str, old_document_id: str) -> bool:
    events = list_events_for_entity(session, "carryover", f"{scope}:{old_document_id}")
    return len(events) > 0


def _engagement_and_consents_signed(packet: Packet) -> ReadinessItem:
    signed = any(event.event == "engagement_signed" for event in packet.timeline)
    reasons = [] if signed else ["no engagement_signed event on the timeline"]
    return ReadinessItem(
        item="engagement_and_consents_signed",
        label="Engagement and consents signed",
        kind="derived",
        met=signed,
        reasons=reasons,
    )


def _all_documents_accounted_for(session: Session, packet: Packet) -> ReadinessItem:
    pending = []
    for document in packet.documents:
        disposition = get_document_disposition(session, document.id)
        status = disposition.disposition if disposition is not None else "pending"
        if status == "pending":
            pending.append(document.id)
    reasons = (
        [] if not pending else [f"{len(pending)} document(s) still pending disposition"]
    )
    return ReadinessItem(
        item="all_documents_accounted_for",
        label="All documents accounted for",
        kind="derived",
        met=not pending,
        reasons=reasons,
    )


def _no_open_cases_or_review_notes(session: Session) -> ReadinessItem:
    open_cases = [c for c in list_cases(session) if c.status in _OPEN_CASE_STATUSES]
    open_notes = [n for n in list_review_notes(session) if n.status != "resolved"]
    reasons = []
    if open_cases:
        reasons.append(f"{len(open_cases)} open case(s)")
    if open_notes:
        reasons.append(f"{len(open_notes)} open review note(s)")
    return ReadinessItem(
        item="no_open_cases_or_review_notes",
        label="No open cases or review notes",
        kind="derived",
        met=not reasons,
        reasons=reasons,
    )


def _scope_has_pending_change(
    session: Session, packet: Packet, rv, scope: Area
) -> bool:
    """Mirrors `routes/areas.py`'s own "signed, change pending" detection
    exactly, including the piece that was missing here until a reviewer-agent
    pass caught it: a decision resolved *after* the scope's last sign-off
    (CONTRACTS.md C2: "A decision -> Change pending") also counts, not just
    a changed engine value, a changed scope, or an unconfirmed carry-over --
    otherwise a scope could read "signed, no pending change" even though a
    case was approved into an adjustment since it was last signed."""
    previous = get_latest_sign_off(session, scope)
    if previous is None:
        return False
    old_rv = packet.return_version(previous.engine_version)
    report = changes_since_sign_off(packet, old_rv, rv, scope)
    if report.value_changed or report.scope_changed:
        return True
    if any(
        not _carryover_confirmed(session, scope, old_id)
        for old_id, _new_id in report.pending_documents
    ):
        return True
    resolved_decision_ids = resolved_decision_ids_in_scope(session, scope)
    current_decisions_fp = compute_fingerprints(
        rv, scope, resolved_decision_ids
    ).decisions
    return previous.decisions_fingerprint != current_decisions_fp


def _no_pending_changes(session: Session, packet: Packet, rv) -> ReadinessItem:
    pending_scopes = [
        scope
        for scope in AREAS
        if _scope_has_pending_change(session, packet, rv, scope)
    ]
    reasons = (
        []
        if not pending_scopes
        else [
            f"{scope} shows a signed, change-pending state" for scope in pending_scopes
        ]
    )
    return ReadinessItem(
        item="no_pending_changes",
        label="No pending changes",
        kind="derived",
        met=not pending_scopes,
        reasons=reasons,
    )


def _reviewer_sign_off(session: Session) -> ReadinessItem:
    unsigned = [
        scope
        for scope in AREAS
        if scope != "tax_computation" and get_latest_sign_off(session, scope) is None
    ]
    reasons = [] if not unsigned else [f"not yet signed: {', '.join(unsigned)}"]
    return ReadinessItem(
        item="reviewer_sign_off",
        label="Reviewer sign-off",
        kind="derived",
        met=not unsigned,
        reasons=reasons,
    )


def _partner_sign_off(session: Session) -> ReadinessItem:
    signed = get_latest_sign_off(session, "tax_computation") is not None
    reasons = [] if signed else ["tax computation has not been signed by the partner"]
    return ReadinessItem(
        item="partner_sign_off",
        label="Partner sign-off",
        kind="derived",
        met=signed,
        reasons=reasons,
    )


def _federal_estimated_payments_posted(packet: Packet) -> Decimal:
    transcripts = packet.tax_agency_records.irs_account_transcript_2025
    if not transcripts:
        return Decimal(0)
    latest = transcripts[-1]
    total = Decimal(0)
    for transaction in latest.get("transactions", []):
        if str(transaction.get("code")) != "670":
            continue
        if (
            "estimated tax payment"
            not in str(transaction.get("description", "")).lower()
        ):
            continue
        amount = parse_money(transaction.get("amount"))
        if amount is not None:
            total += amount
    return total


def _california_estimated_payments_posted(packet: Packet) -> Decimal:
    payments = packet.tax_agency_records.ftb_account.get("tax_year_2025_payments", [])
    total = Decimal(0)
    for payment in payments:
        amount = parse_money(payment.get("amount"))
        if amount is not None:
            total += amount
    return total


def _estimated_payments_agreed(packet: Packet, rv) -> ReadinessItem:
    reasons = []
    federal_line = next(
        (line for line in rv.lines if line.rule == "R-ESTIMATED-PAYMENTS"), None
    )
    if federal_line is not None:
        declared = parse_money(federal_line.value) or Decimal(0)
        posted = _federal_estimated_payments_posted(packet)
        if declared != posted:
            reasons.append(
                f"federal estimated payments declared {declared} vs IRS transcript {posted}"
            )
    california_line = next(
        (line for line in rv.lines if line.rule == "R-CA-ESTIMATED-PAYMENTS"), None
    )
    if california_line is not None:
        declared = parse_money(california_line.value) or Decimal(0)
        posted = _california_estimated_payments_posted(packet)
        if declared != posted:
            reasons.append(
                f"California estimated payments declared {declared} vs FTB account {posted}"
            )
    return ReadinessItem(
        item="estimated_payments_agreed",
        label="Estimated payments agreed to IRS and FTB records",
        kind="derived",
        met=not reasons,
        reasons=reasons,
    )


def _carryovers_agreed(session: Session, packet: Packet, rv) -> ReadinessItem:
    unconfirmed_scopes = []
    for scope in AREAS:
        previous = get_latest_sign_off(session, scope)
        if previous is None:
            continue
        old_rv = packet.return_version(previous.engine_version)
        report = changes_since_sign_off(packet, old_rv, rv, scope)
        if any(
            not _carryover_confirmed(session, scope, old_id)
            for old_id, _new_id in report.pending_documents
        ):
            unconfirmed_scopes.append(scope)
    reasons = (
        []
        if not unconfirmed_scopes
        else [f"unconfirmed carry-over in: {', '.join(unconfirmed_scopes)}"]
    )
    return ReadinessItem(
        item="carryovers_agreed",
        label="Carryovers agreed",
        kind="derived",
        met=not unconfirmed_scopes,
        reasons=reasons,
    )


def _iso(value: datetime | None) -> str | None:
    """SQLite's DateTime type doesn't reliably round-trip tz-awareness
    (same quirk `proofline.db.models._iso` already works around) --
    every timestamp here is written as UTC, so a naive read-back is
    treated as UTC too."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def _attestation_item(session: Session, item: str, label: str) -> ReadinessItem:
    events: list[Event] = list_events_for_entity(session, "readiness_item", item)
    if not events:
        return ReadinessItem(
            item=item,
            label=label,
            kind="attestation",
            met=False,
            reasons=["not yet confirmed"],
        )
    latest = events[-1]
    return ReadinessItem(
        item=item,
        label=label,
        kind="attestation",
        met=True,
        reasons=[],
        confirmed_by=latest.actor_id,
        confirmed_at=_iso(latest.occurred_at),
        note=latest.payload.get("note"),
    )


def readiness_report(session: Session, packet: Packet) -> dict:
    rv = packet.return_versions[-1]
    items = [
        _engagement_and_consents_signed(packet),
        _all_documents_accounted_for(session, packet),
        _no_open_cases_or_review_notes(session),
        _no_pending_changes(session, packet, rv),
        _reviewer_sign_off(session),
        _partner_sign_off(session),
        _estimated_payments_agreed(packet, rv),
        _carryovers_agreed(session, packet, rv),
        *(
            _attestation_item(session, item, label)
            for item, label in ATTESTATION_ITEMS.items()
        ),
    ]
    return {
        "ready_to_file": all(item.met for item in items),
        "items": [
            {
                "item": item.item,
                "label": item.label,
                "kind": item.kind,
                "met": item.met,
                "reasons": item.reasons,
                "confirmed_by": item.confirmed_by,
                "confirmed_at": item.confirmed_at,
                "note": item.note,
            }
            for item in items
        ],
    }
