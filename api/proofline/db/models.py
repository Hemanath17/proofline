from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import Uuid

# JSONB on Postgres (indexable, binary storage); plain JSON everywhere else,
# so the SQLite-backed test fixtures keep working unchanged.
_JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


def _iso(value: datetime | None) -> str | None:
    """SQLite's DateTime type doesn't reliably round-trip whether a stored
    timestamp was timezone-aware, so a value read back from it can come
    back naive even though every timestamp here is written as UTC --
    treating a naive value as UTC here means `to_dict()` compares the same
    whether or not this particular read happened to go through SQLite."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


class Base(DeclarativeBase):
    pass


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_entity", "entity_type", "entity_id"),
        Index("ix_events_seq", "seq"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(_JSON_TYPE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Postgres always fills this from its own identity sequence -- the ORM
    # never supplies it explicitly. SQLite has no equivalent mechanism, so
    # repository.insert_event() assigns a placeholder there; see its
    # comment for why that's safe.
    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=False), nullable=False)
    # Added in Step 4. Nullable so the Step 1 proof-of-deploy row, which
    # predates all of these, stays valid -- every event written through the
    # action service from here on supplies all five.
    actor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String, nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # The entity's revision *after* this event is applied -- None for
    # log-only events (e.g. revealing a sensitive value) that have no
    # current-state row to version.
    revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Business time: when the action happened, as opposed to `created_at`
    # (record time: when we wrote it down). They differ during a replay
    # (Step 8), where an action is recorded today for something that
    # happened on the packet's timeline months ago.
    occurred_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ReviewNote(Base):
    """Current state for one review note. The note's own thread of
    responses lives only in events (`review_note_responded`) -- a growing
    log of "what people did" isn't a point-in-time snapshot, so it has no
    column here; `respond_review_note` still bumps `revision` to serialize
    concurrent writers."""

    __tablename__ = "review_notes"
    __table_args__ = (Index("ix_review_notes_about", "about_type", "about_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    about_type: Mapped[str] = mapped_column(String, nullable=False)
    about_id: Mapped[str] = mapped_column(String, nullable=False)
    opened_by: Mapped[str] = mapped_column(String, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    resolved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution: Mapped[str | None] = mapped_column(String, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Step 5: the note's own text, so the queue/case screens can show it
    # without reading events. Added in migration c1a53e8f9201. Holds the
    # *latest* text (the opening body, or the latest response's body if the
    # note has been responded to) -- the thread of every response still
    # lives only in `review_note_responded` events, per the Step-4 decision
    # that a growing log of "what people said" isn't a point-in-time
    # snapshot.
    body: Mapped[str | None] = mapped_column(String, nullable=True)

    def to_dict(self) -> dict:
        """The one place this shape is written -- shared by the
        review-notes routes and the 409 handler for a stale revision, so
        they can never drift apart."""
        return {
            "id": self.id,
            "about_type": self.about_type,
            "about_id": self.about_id,
            "opened_by": self.opened_by,
            "opened_at": _iso(self.opened_at),
            "status": self.status,
            "resolved_by": self.resolved_by,
            "resolved_at": _iso(self.resolved_at),
            "resolution": self.resolution,
            "revision": self.revision,
            "body": self.body,
        }


class CheckRun(Base):
    """An append-only snapshot of the findings at a decision point. Never
    updated -- `record_check_run` only ever inserts a new row."""

    __tablename__ = "check_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("events.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    return_version: Mapped[str] = mapped_column(String, nullable=False)
    findings: Mapped[list] = mapped_column(_JSON_TYPE, nullable=False)
    failures: Mapped[list] = mapped_column(_JSON_TYPE, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "return_version": self.return_version,
            "findings": self.findings,
            "failures": self.failures,
        }


def _decimal_str(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


class Case(Base):
    """Current state for one case (CONTRACTS.md C1). One row per root
    cause -- `sync_cases_from_findings` (proofline/actions/cases.py) upserts
    by `root_cause_key` so re-running checks never creates a duplicate.
    The finding-shaped fields (observed/expected/.../tax_effect) mirror
    `proofline.checks.models.CheckResult` for an origin="check" case, and
    are filled in directly by whoever opens a hand-made case otherwise."""

    __tablename__ = "cases"
    __table_args__ = (Index("ix_cases_root_cause_key", "root_cause_key", unique=True),)

    case_id: Mapped[str] = mapped_column(String, primary_key=True)
    root_cause_key: Mapped[str] = mapped_column(String, nullable=False)
    origin: Mapped[str] = mapped_column(String, nullable=False)
    origin_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    scope: Mapped[str] = mapped_column(String, nullable=False)
    claims: Mapped[list] = mapped_column(_JSON_TYPE, nullable=False, default=list)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    finding_type: Mapped[str | None] = mapped_column(String, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    assignee_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    check_id: Mapped[str | None] = mapped_column(String, nullable=True)
    check_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_refs: Mapped[list] = mapped_column(
        _JSON_TYPE, nullable=False, default=list
    )
    observed: Mapped[str | None] = mapped_column(String, nullable=True)
    expected: Mapped[str | None] = mapped_column(String, nullable=True)
    limitations: Mapped[str | None] = mapped_column(String, nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(String, nullable=True)
    tax_effect_federal: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    tax_effect_california: Mapped[Decimal | None] = mapped_column(
        Numeric, nullable=True
    )
    tax_effect_kind: Mapped[str | None] = mapped_column(String, nullable=True)
    tax_effect_direction: Mapped[str | None] = mapped_column(String, nullable=True)
    impact_unknown: Mapped[bool] = mapped_column(nullable=False, default=False)
    cleared_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "root_cause_key": self.root_cause_key,
            "origin": self.origin,
            "origin_ref": self.origin_ref,
            "scope": self.scope,
            "claims": self.claims,
            "severity": self.severity,
            "finding_type": self.finding_type,
            "priority": self.priority,
            "assignee_id": self.assignee_id,
            "status": self.status,
            "revision": self.revision,
            "check_id": self.check_id,
            "check_version": self.check_version,
            "evidence_refs": self.evidence_refs,
            "observed": self.observed,
            "expected": self.expected,
            "limitations": self.limitations,
            "recommended_action": self.recommended_action,
            "tax_effect": (
                None
                if self.tax_effect_federal is None
                else {
                    "federal": _decimal_str(self.tax_effect_federal),
                    "california": _decimal_str(self.tax_effect_california),
                    "kind": self.tax_effect_kind,
                    "direction": self.tax_effect_direction,
                }
            ),
            "impact_unknown": self.impact_unknown,
            "cleared_reason": self.cleared_reason,
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
        }


class CaseProposal(Base):
    """One revision of a case's proposed resolution. Append-only: a new
    `submit_proposal` always inserts a new row with the next
    `revision_number`, never edits an existing one (CONTRACTS.md C1: "every
    revision of a proposal is kept")."""

    __tablename__ = "case_proposals"
    __table_args__ = (
        Index("ix_case_proposals_case_id", "case_id"),
        Index(
            "ix_case_proposals_case_revision", "case_id", "revision_number", unique=True
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String, ForeignKey("cases.case_id"), nullable=False
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    resolution_type: Mapped[str] = mapped_column(String, nullable=False)
    fields: Mapped[dict] = mapped_column(_JSON_TYPE, nullable=False, default=dict)
    evidence_refs: Mapped[list] = mapped_column(
        _JSON_TYPE, nullable=False, default=list
    )
    proposed_by: Mapped[str] = mapped_column(String, nullable=False)
    proposed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "case_id": self.case_id,
            "revision_number": self.revision_number,
            "resolution_type": self.resolution_type,
            "fields": self.fields,
            "evidence_refs": self.evidence_refs,
            "proposed_by": self.proposed_by,
            "proposed_at": _iso(self.proposed_at),
        }


class CaseDecision(Base):
    """One decision on a case, pointing at the exact proposal revision it
    applies to (CONTRACTS.md C1: "a decision always names the revision it
    applies to"). Append-only, like `CaseProposal`."""

    __tablename__ = "case_decisions"
    __table_args__ = (Index("ix_case_decisions_case_id", "case_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String, ForeignKey("cases.case_id"), nullable=False
    )
    proposal_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decision: Mapped[str] = mapped_column(String, nullable=False)
    decided_by: Mapped[str] = mapped_column(String, nullable=False)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    note: Mapped[str | None] = mapped_column(String, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "case_id": self.case_id,
            "proposal_revision": self.proposal_revision,
            "decision": self.decision,
            "decided_by": self.decided_by,
            "decided_at": _iso(self.decided_at),
            "note": self.note,
        }


class LastSeen(Base):
    """When an actor last opened a case/area/document/queue item. UI state,
    not a workpaper event (docs/UX.md "Since you last looked") -- no
    immutability trigger, no revision check, plain upsert via
    `proofline.db.repository.record_last_seen`."""

    __tablename__ = "last_seen"
    __table_args__ = (PrimaryKeyConstraint("actor_id", "entity_type", "entity_id"),)

    actor_id: Mapped[str] = mapped_column(String, nullable=False)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[str] = mapped_column(String, nullable=False)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Adjustment(Base):
    """One approved overlay on a claim (CONTRACTS.md C3). Created only
    when the case that proposed it actually reaches `resolved`
    (`proofline.actions.cases.approve`/`partner_approve`) -- its mere
    existence is what "approved" means, so there's no separate status
    column. Append-only, like `CaseProposal`/`CaseDecision`."""

    __tablename__ = "adjustments"
    __table_args__ = (Index("ix_adjustments_claim_key", "claim_key"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    claim_key: Mapped[str] = mapped_column(String, nullable=False)
    old_value: Mapped[str] = mapped_column(String, nullable=False)
    new_value: Mapped[str] = mapped_column(String, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(
        _JSON_TYPE, nullable=False, default=list
    )
    case_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("cases.case_id"), nullable=True
    )
    decision_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("case_decisions.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "claim_key": self.claim_key,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "evidence_refs": self.evidence_refs,
            "case_id": self.case_id,
            "decision_id": self.decision_id,
            "created_at": _iso(self.created_at),
        }


class SignOff(Base):
    """One version of a scope's sign-off (CONTRACTS.md C2). Append-only:
    a new version is always a new row, and the previous version's row is
    never touched -- "version n+1 is version n plus that change. Both are
    kept." Unique on (scope, version), never updated in place."""

    __tablename__ = "sign_offs"
    __table_args__ = (
        Index("ix_sign_offs_scope_version", "scope", "version", unique=True),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    scope: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    signed_by: Mapped[str] = mapped_column(String, nullable=False)
    signed_role: Mapped[str] = mapped_column(String, nullable=False)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    engine_version: Mapped[str] = mapped_column(String, nullable=False)
    active_adjustment_ids: Mapped[list] = mapped_column(
        _JSON_TYPE, nullable=False, default=list
    )
    check_run_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("check_runs.id"), nullable=True
    )
    evidence_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    values_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    decisions_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    scope_fingerprint: Mapped[str] = mapped_column(String, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "scope": self.scope,
            "version": self.version,
            "signed_by": self.signed_by,
            "signed_role": self.signed_role,
            "signed_at": _iso(self.signed_at),
            "engine_version": self.engine_version,
            "active_adjustment_ids": self.active_adjustment_ids,
            "check_run_id": self.check_run_id,
            "evidence_fingerprint": self.evidence_fingerprint,
            "values_fingerprint": self.values_fingerprint,
            "decisions_fingerprint": self.decisions_fingerprint,
            "scope_fingerprint": self.scope_fingerprint,
        }


class DocumentDisposition(Base):
    """One document's disposition (CONTRACTS.md C4). Current state, one
    row per document, defaulting to `pending` -- rules propose, the
    preparer confirms via `proofline.actions.disposition.confirm_disposition`."""

    __tablename__ = "document_dispositions"

    document_id: Mapped[str] = mapped_column(String, primary_key=True)
    disposition: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    confirmed_by: Mapped[str | None] = mapped_column(String, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    def to_dict(self) -> dict:
        return {
            "document_id": self.document_id,
            "disposition": self.disposition,
            "reason": self.reason,
            "confirmed_by": self.confirmed_by,
            "confirmed_at": _iso(self.confirmed_at),
            "revision": self.revision,
        }


class FiledRecord(Base):
    """One jurisdiction's accepted filing (CONTRACTS.md C5, invariant I6).
    Written once, only when `proofline.actions.filing.submit_filing` records
    an accepted result -- never on a rejection, never updated afterward.
    `amends_filed_record_id` is a nullable self-reference so a future
    amendment package can point at the filed record it amends (Step 9+);
    nothing writes it yet. The database trigger that refuses UPDATE/DELETE/
    TRUNCATE is created in its own migration, the same way `events`' is --
    see that migration's comment for why it's Postgres-only."""

    __tablename__ = "filed_records"
    __table_args__ = (
        Index("ix_filed_records_jurisdiction", "jurisdiction", unique=True),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    jurisdiction: Mapped[str] = mapped_column(String, nullable=False)
    package_reference: Mapped[str] = mapped_column(String, nullable=False)
    amounts_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    identity_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    submission_event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("events.id"), nullable=False
    )
    amends_filed_record_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("filed_records.id"), nullable=True
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "jurisdiction": self.jurisdiction,
            "package_reference": self.package_reference,
            "amounts_fingerprint": self.amounts_fingerprint,
            "identity_fingerprint": self.identity_fingerprint,
            "accepted_at": _iso(self.accepted_at),
            "submission_event_id": str(self.submission_event_id),
            "amends_filed_record_id": self.amends_filed_record_id,
        }


class ClaimVerification(Base):
    """A human review-state marker on one claim (docs/UX.md "Verified ·
    DO"): who verified it, in what role, and when. Written only by
    `proofline.actions.bulk.bulk_verify` (and removed only by
    `undo_bulk_verify`) -- log-only like `LastSeen`/`carryover_confirmed`,
    no revision check, since verifying is idempotent and the group action
    that wrote it is itself recorded as an event (`bulk_claims_verified`)
    that undo reverses by writing a new event, never by editing this row
    in place."""

    __tablename__ = "claim_verifications"

    claim_key: Mapped[str] = mapped_column(String, primary_key=True)
    verified_by: Mapped[str] = mapped_column(String, nullable=False)
    verified_role: Mapped[str] = mapped_column(String, nullable=False)
    verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    verified_by_event_id: Mapped[str | None] = mapped_column(String, nullable=True)

    def to_dict(self) -> dict:
        return {
            "claim_key": self.claim_key,
            "verified_by": self.verified_by,
            "verified_role": self.verified_role,
            "verified_at": _iso(self.verified_at),
            "verified_by_event_id": self.verified_by_event_id,
        }
