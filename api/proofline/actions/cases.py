"""Cases (CONTRACTS.md C1): the schema, the sync from check findings, every
transition in the table, and the evidence-requirement validation for each
resolution type.

Every transition a person calls goes through `perform()` like any other
action: permission check, then the "only when" condition, then the
compare-and-set, then the event. `clear` is the one transition whose "Who"
is System -- it's never exposed as its own route; it only happens inside
`sync_cases_from_findings` (itself called from the `sync_cases` action, so
it's still one transaction with its event, same as everything else,
CONTRACTS.md Storage), written with a synthetic system actor (`SYSTEM_ACTOR`,
not in the packet, like the AI assistant).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from proofline.actions.errors import ActionConflict, ActionValidationError, require
from proofline.actions.results import ActionResult
from proofline.analysis.grouping import root_cause_key
from proofline.checks.models import CheckResult
from proofline.checks.runner import run_all_checks
from proofline.db.canonical import prepare_payload_for_storage
from proofline.db.models import Adjustment, Case, CaseDecision, CaseProposal
from proofline.db.repository import (
    EntityNotFound,
    apply_revision_cas,
    get_case,
    get_case_by_root_cause_key,
    insert_adjustment,
    insert_case,
    insert_case_decision,
    insert_case_proposal,
    insert_event,
    list_case_proposals,
    list_cases,
)
from proofline.packet import Packet
from proofline.security.actors import Actor
from proofline.security.permissions import check_permission

SYSTEM_ACTOR = Actor(id="system", name="System", role="system", clearance=False)

_TAX_EFFECT_PARTNER_THRESHOLD = 1000

# The fields each resolution type needs before anyone reviews it
# (CONTRACTS.md C1). `evidence_refs` (at least one, checked separately
# below) is required for every type except a judgment, which stands on its
# own authority/approval rather than a packet reference. `adjust_number`'s
# `adjustments` is a list, not a flat field -- a root cause can (and in
# the RSU case does) bundle several claims into one proposal, so its
# shape is validated separately by `_validate_adjustments`.
_RESOLUTION_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "resolve_evidence_conflict": ("evidence_a", "evidence_b", "chosen", "reason"),
    "record_judgment": ("reasoning", "authority", "approved_by"),
    "adjust_number": (),
    "mark_legitimate": ("reason",),
}
_RESOLUTION_TYPES = frozenset(_RESOLUTION_REQUIRED_FIELDS)
_CLIENT_EVIDENCE_PREFIXES = ("qa-", "msg-", "call-")


def _is_client_evidence(ref: str) -> bool:
    return any(ref.startswith(prefix) for prefix in _CLIENT_EVIDENCE_PREFIXES)


def _validate_adjustments(fields: dict[str, Any]) -> None:
    adjustments = fields.get("adjustments")
    if not isinstance(adjustments, list) or not adjustments:
        raise ActionValidationError(
            "adjust_number needs a non-empty 'adjustments' list, each with "
            "claim, old_value and new_value"
        )
    for entry in adjustments:
        if not isinstance(entry, dict):
            raise ActionValidationError("each adjustment must be an object")
        for key in ("claim", "old_value", "new_value"):
            if entry.get(key) in (None, ""):
                raise ActionValidationError(f"each adjustment needs {key!r}")


def validate_resolution_fields(resolution_type: str, fields: dict[str, Any]) -> None:
    if resolution_type not in _RESOLUTION_TYPES:
        raise ActionValidationError(
            f"resolution_type must be one of {sorted(_RESOLUTION_TYPES)}"
        )
    if resolution_type == "adjust_number":
        _validate_adjustments(fields)
        return
    for field_name in _RESOLUTION_REQUIRED_FIELDS[resolution_type]:
        require(fields, field_name)


def _case_from_finding(case_id: str, finding: CheckResult) -> Case:
    tax_effect = finding.tax_effect
    return Case(
        case_id=case_id,
        root_cause_key=root_cause_key(finding),
        origin="check",
        origin_ref=finding.check_id,
        scope=finding.area,
        claims=[str(claim) for claim in finding.claims],
        severity=finding.severity,
        finding_type=finding.finding_type,
        priority=_PRIORITY_BY_SEVERITY.get(finding.severity, 3),
        status="open",
        revision=1,
        check_id=finding.check_id,
        check_version=finding.check_version,
        evidence_refs=list(finding.evidence_refs),
        observed=finding.observed,
        expected=finding.expected,
        limitations=finding.limitations,
        recommended_action=finding.recommended_action,
        tax_effect_federal=None if tax_effect is None else tax_effect.federal,
        tax_effect_california=None if tax_effect is None else tax_effect.california,
        tax_effect_kind=None if tax_effect is None else tax_effect.kind,
        tax_effect_direction=None if tax_effect is None else tax_effect.direction,
        impact_unknown=finding.impact_unknown,
    )


_PRIORITY_BY_SEVERITY = {
    "blocks_filing": 0,
    "penalty_risk": 1,
    "tax_amount": 2,
    "info": 3,
}


def sync_cases_from_findings(
    session: Session,
    findings: list[CheckResult],
    *,
    occurred_at: datetime | None = None,
) -> list[Case]:
    """Upserts one case per root cause from the current findings, and
    clears any open/investigating check-origin case whose root cause no
    longer appears (CONTRACTS.md C1: "a finding that stops firing clears
    its case with the reason saved"). Returns every case touched (newly
    opened or re-synced); does not touch hand-opened cases at all."""
    when = occurred_at or datetime.now(UTC)
    seen_root_causes: set[str] = set()
    touched: list[Case] = []

    for finding in findings:
        key = root_cause_key(finding)
        seen_root_causes.add(key)
        existing = get_case_by_root_cause_key(session, key)
        if existing is not None:
            touched.append(existing)
            continue
        case_id = f"case-{uuid.uuid4()}"
        case = _case_from_finding(case_id, finding)
        insert_case(session, case)
        insert_event(
            session,
            "case_opened",
            {
                "origin": "check",
                "root_cause_key": key,
                # The full finding, so rebuild can reconstruct the case row
                # exactly (CONTRACTS.md Storage, I5) without having to
                # rerun the check that produced it -- the check's logic can
                # change over time, but an old event must stay replayable.
                "finding": prepare_payload_for_storage(finding.model_dump(mode="json")),
            },
            actor_id=SYSTEM_ACTOR.id,
            entity_type="case",
            entity_id=case_id,
            revision=1,
            occurred_at=when,
        )
        touched.append(case)

    for case in list_cases(session):
        if case.origin != "check":
            continue
        if case.root_cause_key in seen_root_causes:
            continue
        if case.status not in ("open", "investigating"):
            continue
        updated = apply_revision_cas(
            session,
            Case,
            case.case_id,
            case.revision,
            {"status": "cleared", "cleared_reason": "the finding stopped firing"},
        )
        insert_event(
            session,
            "case_cleared",
            {"reason": "the finding stopped firing"},
            actor_id=SYSTEM_ACTOR.id,
            entity_type="case",
            entity_id=case.case_id,
            revision=updated.revision,
            occurred_at=when,
        )
        touched.append(updated)

    return touched


def open_case_by_hand(
    session: Session,
    actor: Actor,
    *,
    entity_id: str | None,
    expected_revision: int | None,
    payload: dict[str, Any],
    occurred_at: datetime | None,
    packet: Packet | None = None,
) -> ActionResult:
    """A case opened by a preparer, reviewer, client, or from a document /
    completeness gap / agency record -- CONTRACTS.md C1's non-check
    origins. `origin_ref` must be supplied by the caller and is unique
    enough (a document id, a notice id, a fresh id) to make a stable
    root-cause key on its own."""
    check_permission(actor, "open_case_by_hand")
    origin = require(payload, "origin")
    if origin not in {
        "preparer",
        "reviewer",
        "client",
        "document",
        "completeness",
        "agency",
    }:
        raise ActionValidationError(
            "origin must be one of preparer, reviewer, client, document, "
            "completeness, agency"
        )
    origin_ref = require(payload, "origin_ref")
    scope = require(payload, "scope")
    severity = require(payload, "severity")
    observed = require(payload, "observed")
    expected = require(payload, "expected")
    key = f"hand:{origin}:{origin_ref}"
    if get_case_by_root_cause_key(session, key) is not None:
        raise ActionConflict("a case already exists for this origin_ref", current=None)
    when = occurred_at or datetime.now(UTC)
    case_id = f"case-{uuid.uuid4()}"
    case = Case(
        case_id=case_id,
        root_cause_key=key,
        origin=origin,
        origin_ref=origin_ref,
        scope=scope,
        claims=payload.get("claims", []),
        severity=severity,
        finding_type=None,
        priority=_PRIORITY_BY_SEVERITY.get(severity, 3),
        assignee_id=payload.get("assignee_id"),
        status="open",
        revision=1,
        evidence_refs=payload.get("evidence_refs", []),
        observed=observed,
        expected=expected,
        limitations=payload.get("limitations"),
        recommended_action=payload.get("recommended_action"),
        impact_unknown=bool(payload.get("impact_unknown", True)),
    )
    insert_case(session, case)
    event = insert_event(
        session,
        "case_opened",
        {
            "origin": origin,
            "origin_ref": origin_ref,
            "root_cause_key": key,
            "scope": scope,
            "claims": case.claims,
            "severity": severity,
            "observed": observed,
            "expected": expected,
            "evidence_refs": case.evidence_refs,
            "limitations": case.limitations,
            "recommended_action": case.recommended_action,
            "assignee_id": case.assignee_id,
            "impact_unknown": case.impact_unknown,
        },
        actor_id=actor.id,
        entity_type="case",
        entity_id=case_id,
        revision=1,
        occurred_at=when,
    )
    return ActionResult(event=event, current_state=case)


def _get_case_or_404(session: Session, case_id: str | None) -> Case:
    if case_id is None:
        raise ActionValidationError("entity_id (the case_id) is required")
    case = get_case(session, case_id)
    if case is None:
        raise EntityNotFound(case_id)
    return case


def _require_expected_revision(expected_revision: int | None) -> int:
    if expected_revision is None:
        raise ActionValidationError("expected_revision is required")
    return expected_revision


def _transition(
    session: Session,
    case: Case,
    expected_revision: int,
    *,
    new_status: str,
    event_type: str,
    event_payload: dict[str, Any],
    actor: Actor,
    when: datetime,
    extra_values: dict[str, Any] | None = None,
) -> ActionResult:
    values = {"status": new_status, **(extra_values or {})}
    updated = apply_revision_cas(session, Case, case.case_id, expected_revision, values)
    event = insert_event(
        session,
        event_type,
        event_payload,
        actor_id=actor.id,
        entity_type="case",
        entity_id=case.case_id,
        revision=updated.revision,
        occurred_at=when,
    )
    return ActionResult(event=event, current_state=updated)


def pick_up(
    session: Session,
    actor: Actor,
    *,
    entity_id: str | None,
    expected_revision: int | None,
    payload: dict[str, Any],
    occurred_at: datetime | None,
    packet: Packet | None = None,
) -> ActionResult:
    check_permission(actor, "pick_up")
    case = _get_case_or_404(session, entity_id)
    revision = _require_expected_revision(expected_revision)
    if case.status != "open":
        raise ActionConflict(
            f"case is {case.status!r}, not open -- pick_up only applies to an open case",
            current=case.to_dict(),
        )
    when = occurred_at or datetime.now(UTC)
    return _transition(
        session,
        case,
        revision,
        new_status="investigating",
        event_type="case_picked_up",
        event_payload={},
        actor=actor,
        when=when,
        extra_values={"assignee_id": actor.id},
    )


def ask_client(
    session: Session,
    actor: Actor,
    *,
    entity_id: str | None,
    expected_revision: int | None,
    payload: dict[str, Any],
    occurred_at: datetime | None,
    packet: Packet | None = None,
) -> ActionResult:
    check_permission(actor, "ask_client")
    case = _get_case_or_404(session, entity_id)
    revision = _require_expected_revision(expected_revision)
    question = require(payload, "question")
    if case.status != "investigating":
        raise ActionConflict(
            f"case is {case.status!r}, not investigating -- ask_client only "
            "applies while investigating",
            current=case.to_dict(),
        )
    when = occurred_at or datetime.now(UTC)
    return _transition(
        session,
        case,
        revision,
        new_status="waiting_on_client",
        event_type="case_client_asked",
        event_payload={"question": question},
        actor=actor,
        when=when,
    )


def client_answered(
    session: Session,
    actor: Actor,
    *,
    entity_id: str | None,
    expected_revision: int | None,
    payload: dict[str, Any],
    occurred_at: datetime | None,
    packet: Packet | None = None,
) -> ActionResult:
    check_permission(actor, "client_answered")
    case = _get_case_or_404(session, entity_id)
    revision = _require_expected_revision(expected_revision)
    evidence_ref = require(payload, "evidence_ref")
    if case.status != "waiting_on_client":
        raise ActionConflict(
            f"case is {case.status!r}, not waiting_on_client", current=case.to_dict()
        )
    when = occurred_at or datetime.now(UTC)
    new_evidence = [*case.evidence_refs, evidence_ref]
    return _transition(
        session,
        case,
        revision,
        new_status="investigating",
        event_type="case_client_answered",
        event_payload={"evidence_ref": evidence_ref},
        actor=actor,
        when=when,
        extra_values={"evidence_refs": new_evidence},
    )


def submit_proposal(
    session: Session,
    actor: Actor,
    *,
    entity_id: str | None,
    expected_revision: int | None,
    payload: dict[str, Any],
    occurred_at: datetime | None,
    packet: Packet | None = None,
) -> ActionResult:
    check_permission(actor, "submit_proposal")
    case = _get_case_or_404(session, entity_id)
    revision = _require_expected_revision(expected_revision)
    if case.status != "investigating":
        raise ActionConflict(
            f"case is {case.status!r}, not investigating -- submit_proposal only "
            "applies while investigating",
            current=case.to_dict(),
        )
    resolution_type = require(payload, "resolution_type")
    fields = payload.get("fields", {})
    validate_resolution_fields(resolution_type, fields)
    evidence_refs = payload.get("evidence_refs", [])
    if resolution_type != "record_judgment" and not evidence_refs:
        raise ActionValidationError(
            f"{resolution_type} needs at least one piece of supporting evidence"
        )
    if resolution_type == "resolve_evidence_conflict":
        chosen_ref = (
            fields["evidence_a"] if fields["chosen"] == "a" else fields["evidence_b"]
        )
        fields = {**fields, "client_evidence_flagged": _is_client_evidence(chosen_ref)}

    existing_proposals = list_case_proposals(session, case.case_id)
    next_revision = (
        existing_proposals[-1].revision_number if existing_proposals else 0
    ) + 1
    when = occurred_at or datetime.now(UTC)
    proposal_id = f"proposal-{uuid.uuid4()}"
    proposal = CaseProposal(
        id=proposal_id,
        case_id=case.case_id,
        revision_number=next_revision,
        resolution_type=resolution_type,
        fields=fields,
        evidence_refs=evidence_refs,
        proposed_by=actor.id,
        proposed_at=when,
    )
    insert_case_proposal(session, proposal)

    updated = apply_revision_cas(
        session, Case, case.case_id, revision, {"status": "in_review"}
    )
    event = insert_event(
        session,
        "case_proposal_submitted",
        {
            "proposal_id": proposal_id,
            "revision_number": next_revision,
            "resolution_type": resolution_type,
            "fields": fields,
            "evidence_refs": evidence_refs,
        },
        actor_id=actor.id,
        entity_type="case",
        entity_id=case.case_id,
        revision=updated.revision,
        occurred_at=when,
    )
    return ActionResult(event=event, current_state=updated)


def _latest_proposal(session: Session, case: Case) -> CaseProposal:
    proposals = list_case_proposals(session, case.case_id)
    if not proposals:
        raise ActionConflict(
            "case has no proposal to decide on", current=case.to_dict()
        )
    return proposals[-1]


def _require_not_own_work(actor: Actor, proposal: CaseProposal) -> None:
    if actor.id == proposal.proposed_by:
        raise ActionConflict(
            "you proposed this. Nobody reviews their own work.", current=None
        )


def _create_adjustments_for_resolved_case(
    session: Session,
    case: Case,
    proposal: CaseProposal,
    decision_id: str,
    when: datetime,
) -> list[str]:
    """Only an `adjust_number` proposal on a case that has just reached
    `resolved` creates `Adjustment` rows (CONTRACTS.md C3: "an approved
    adjustment overlay") -- a case still `awaiting_partner` hasn't been
    approved yet, so `approve()` only calls this when `new_status ==
    "resolved"`. Returns the new rows' ids, so the caller's event payload
    can carry them for rebuild fidelity (I5), same reason
    `case_proposal_submitted` carries its `proposal_id`."""
    if proposal.resolution_type != "adjust_number":
        return []
    adjustment_ids: list[str] = []
    for entry in proposal.fields.get("adjustments", []):
        adjustment_id = f"adjustment-{uuid.uuid4()}"
        insert_adjustment(
            session,
            Adjustment(
                id=adjustment_id,
                claim_key=str(entry["claim"]),
                old_value=str(entry["old_value"]),
                new_value=str(entry["new_value"]),
                evidence_refs=proposal.evidence_refs,
                case_id=case.case_id,
                decision_id=decision_id,
                created_at=when,
            ),
        )
        adjustment_ids.append(adjustment_id)
    return adjustment_ids


def return_proposal(
    session: Session,
    actor: Actor,
    *,
    entity_id: str | None,
    expected_revision: int | None,
    payload: dict[str, Any],
    occurred_at: datetime | None,
    packet: Packet | None = None,
) -> ActionResult:
    check_permission(actor, "return")
    case = _get_case_or_404(session, entity_id)
    revision = _require_expected_revision(expected_revision)
    note = require(payload, "note")
    if case.status != "in_review":
        raise ActionConflict(
            f"case is {case.status!r}, not in_review", current=case.to_dict()
        )
    proposal = _latest_proposal(session, case)
    _require_not_own_work(actor, proposal)
    when = occurred_at or datetime.now(UTC)
    decision_id = f"decision-{uuid.uuid4()}"
    insert_case_decision(
        session,
        CaseDecision(
            id=decision_id,
            case_id=case.case_id,
            proposal_revision=proposal.revision_number,
            decision="return",
            decided_by=actor.id,
            decided_at=when,
            note=note,
        ),
    )
    return _transition(
        session,
        case,
        revision,
        new_status="investigating",
        event_type="case_returned",
        event_payload={
            "decision_id": decision_id,
            "proposal_revision": proposal.revision_number,
            "note": note,
        },
        actor=actor,
        when=when,
    )


def approve(
    session: Session,
    actor: Actor,
    *,
    entity_id: str | None,
    expected_revision: int | None,
    payload: dict[str, Any],
    occurred_at: datetime | None,
    packet: Packet | None = None,
) -> ActionResult:
    check_permission(actor, "approve")
    case = _get_case_or_404(session, entity_id)
    revision = _require_expected_revision(expected_revision)
    if case.status != "in_review":
        raise ActionConflict(
            f"case is {case.status!r}, not in_review", current=case.to_dict()
        )
    proposal = _latest_proposal(session, case)
    _require_not_own_work(actor, proposal)

    federal = abs(case.tax_effect_federal or 0)
    california = abs(case.tax_effect_california or 0)
    over_threshold = (
        federal > _TAX_EFFECT_PARTNER_THRESHOLD
        or california > _TAX_EFFECT_PARTNER_THRESHOLD
    )
    new_status = "awaiting_partner" if over_threshold else "resolved"

    when = occurred_at or datetime.now(UTC)
    decision_id = f"decision-{uuid.uuid4()}"
    note = payload.get("note")
    insert_case_decision(
        session,
        CaseDecision(
            id=decision_id,
            case_id=case.case_id,
            proposal_revision=proposal.revision_number,
            decision="approve",
            decided_by=actor.id,
            decided_at=when,
            note=note,
        ),
    )
    adjustment_ids = (
        _create_adjustments_for_resolved_case(
            session, case, proposal, decision_id, when
        )
        if new_status == "resolved"
        else []
    )
    return _transition(
        session,
        case,
        revision,
        new_status=new_status,
        event_type="case_approved",
        event_payload={
            "decision_id": decision_id,
            "proposal_revision": proposal.revision_number,
            "next_status": new_status,
            "note": note,
            "adjustment_ids": adjustment_ids,
        },
        actor=actor,
        when=when,
    )


def partner_approve(
    session: Session,
    actor: Actor,
    *,
    entity_id: str | None,
    expected_revision: int | None,
    payload: dict[str, Any],
    occurred_at: datetime | None,
    packet: Packet | None = None,
) -> ActionResult:
    check_permission(actor, "partner_approve")
    case = _get_case_or_404(session, entity_id)
    revision = _require_expected_revision(expected_revision)
    if case.status != "awaiting_partner":
        raise ActionConflict(
            f"case is {case.status!r}, not awaiting_partner", current=case.to_dict()
        )
    proposal = _latest_proposal(session, case)
    when = occurred_at or datetime.now(UTC)
    decision_id = f"decision-{uuid.uuid4()}"
    note = payload.get("note")
    insert_case_decision(
        session,
        CaseDecision(
            id=decision_id,
            case_id=case.case_id,
            proposal_revision=proposal.revision_number,
            decision="partner_approve",
            decided_by=actor.id,
            decided_at=when,
            note=note,
        ),
    )
    adjustment_ids = _create_adjustments_for_resolved_case(
        session, case, proposal, decision_id, when
    )
    return _transition(
        session,
        case,
        revision,
        new_status="resolved",
        event_type="case_partner_approved",
        event_payload={
            "decision_id": decision_id,
            "proposal_revision": proposal.revision_number,
            "note": note,
            "adjustment_ids": adjustment_ids,
        },
        actor=actor,
        when=when,
    )


def partner_return(
    session: Session,
    actor: Actor,
    *,
    entity_id: str | None,
    expected_revision: int | None,
    payload: dict[str, Any],
    occurred_at: datetime | None,
    packet: Packet | None = None,
) -> ActionResult:
    check_permission(actor, "partner_return")
    case = _get_case_or_404(session, entity_id)
    revision = _require_expected_revision(expected_revision)
    note = require(payload, "note")
    if case.status != "awaiting_partner":
        raise ActionConflict(
            f"case is {case.status!r}, not awaiting_partner", current=case.to_dict()
        )
    proposal = _latest_proposal(session, case)
    when = occurred_at or datetime.now(UTC)
    decision_id = f"decision-{uuid.uuid4()}"
    insert_case_decision(
        session,
        CaseDecision(
            id=decision_id,
            case_id=case.case_id,
            proposal_revision=proposal.revision_number,
            decision="partner_return",
            decided_by=actor.id,
            decided_at=when,
            note=note,
        ),
    )
    return _transition(
        session,
        case,
        revision,
        new_status="investigating",
        event_type="case_partner_returned",
        event_payload={
            "decision_id": decision_id,
            "proposal_revision": proposal.revision_number,
            "note": note,
        },
        actor=actor,
        when=when,
    )


def reopen(
    session: Session,
    actor: Actor,
    *,
    entity_id: str | None,
    expected_revision: int | None,
    payload: dict[str, Any],
    occurred_at: datetime | None,
    packet: Packet | None = None,
) -> ActionResult:
    check_permission(actor, "reopen")
    case = _get_case_or_404(session, entity_id)
    revision = _require_expected_revision(expected_revision)
    reason = require(payload, "reason")
    if case.status != "resolved":
        raise ActionConflict(
            f"case is {case.status!r}, not resolved", current=case.to_dict()
        )
    when = occurred_at or datetime.now(UTC)
    return _transition(
        session,
        case,
        revision,
        new_status="investigating",
        event_type="case_reopened",
        event_payload={"reason": reason},
        actor=actor,
        when=when,
    )


def reassign(
    session: Session,
    actor: Actor,
    *,
    entity_id: str | None,
    expected_revision: int | None,
    payload: dict[str, Any],
    occurred_at: datetime | None,
    packet: Packet | None = None,
) -> ActionResult:
    check_permission(actor, "reassign")
    case = _get_case_or_404(session, entity_id)
    revision = _require_expected_revision(expected_revision)
    assignee_id = require(payload, "assignee_id")
    if case.status in ("resolved", "cleared"):
        raise ActionConflict(
            f"case is {case.status!r} -- only an open case can be reassigned",
            current=case.to_dict(),
        )
    when = occurred_at or datetime.now(UTC)
    return _transition(
        session,
        case,
        revision,
        new_status=case.status,
        event_type="case_reassigned",
        event_payload={"assignee_id": assignee_id},
        actor=actor,
        when=when,
        extra_values={"assignee_id": assignee_id},
    )


class _SyncResult:
    """Wraps the cases touched by one sync, so `sync_cases`'s ActionResult
    has a `.to_dict()` like every other current_state, even though a sync
    touches many cases rather than one entity."""

    def __init__(self, cases: list[Case]):
        self.cases = cases

    def to_dict(self) -> dict:
        return {"cases": [case.to_dict() for case in self.cases]}


def sync_cases(
    session: Session,
    actor: Actor,
    *,
    entity_id: str | None,
    expected_revision: int | None,
    payload: dict[str, Any],
    occurred_at: datetime | None,
    packet: Packet | None = None,
) -> ActionResult:
    """Runs every check and upserts/clears cases from the findings
    (CONTRACTS.md C1). Staff-only, since it's a workpaper action with its
    own event, not a passive read."""
    check_permission(actor, "sync_cases")
    if packet is None:
        raise ActionValidationError("sync_cases needs the packet")
    when = occurred_at or datetime.now(UTC)
    run_result = run_all_checks(packet)
    touched = sync_cases_from_findings(session, run_result.findings, occurred_at=when)
    event = insert_event(
        session,
        "cases_synced",
        {"cases_touched": [case.case_id for case in touched]},
        actor_id=actor.id,
        entity_type="case_sync",
        entity_id=f"sync-{uuid.uuid4()}",
        revision=None,
        occurred_at=when,
    )
    return ActionResult(event=event, current_state=_SyncResult(touched))
