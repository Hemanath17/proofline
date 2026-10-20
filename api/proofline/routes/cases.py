"""The review queue (S1) and case detail (S2) API -- CONTRACTS.md C1,
docs/UX.md S1/S2. Role-aware tabs, severity grouping, "why it's here", and
one POST per C1 transition, all through `perform()`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from proofline.actions.service import perform
from proofline.ai.suggestions import list_case_suggestions
from proofline.analysis.changes import (
    case_change_summary,
    cases_needing_actor,
    changed_since_last_seen,
)
from proofline.db.connection import get_session
from proofline.db.models import Case
from proofline.db.repository import (
    get_case,
    get_last_seen,
    list_case_decisions,
    list_case_proposals,
    list_cases,
    list_events_for_entity,
    record_last_seen,
)
from proofline.packet import load_packet
from proofline.security.actors import Actor, load_actors
from proofline.security.dependencies import get_current_actor, require_non_client
from proofline.security.redact import redact_for_actor

router = APIRouter()

_OPEN_STATUSES = {
    "open",
    "investigating",
    "waiting_on_client",
    "in_review",
    "awaiting_partner",
}
_SEVERITY_GROUP_ORDER = ("blocks_filing", "tax_amount", "penalty_risk", "info")


class OpenCaseRequest(BaseModel):
    origin: str
    origin_ref: str
    scope: str
    severity: str
    observed: str
    expected: str
    claims: list[str] = []
    evidence_refs: list[str] = []
    limitations: str | None = None
    recommended_action: str | None = None
    assignee_id: str | None = None
    impact_unknown: bool = True


class RevisionedRequest(BaseModel):
    expected_revision: int


class AskClientRequest(RevisionedRequest):
    question: str


class ClientAnsweredRequest(RevisionedRequest):
    evidence_ref: str


class SubmitProposalRequest(RevisionedRequest):
    resolution_type: str
    fields: dict[str, Any] = {}
    evidence_refs: list[str] = []


class NoteRequest(RevisionedRequest):
    note: str


class ApproveRequest(RevisionedRequest):
    note: str | None = None


class ReopenRequest(RevisionedRequest):
    reason: str


class ReassignRequest(RevisionedRequest):
    assignee_id: str


def _case_row(session: Session, actor: Actor, case: Case) -> dict:
    last_seen_at = get_last_seen(session, actor.id, "case", case.case_id)
    proposals = list_case_proposals(session, case.case_id)
    decisions = list_case_decisions(session, case.case_id)
    row = case.to_dict()
    row["changed_since_last_seen"] = changed_since_last_seen(
        case.updated_at, last_seen_at
    )
    row["change_summary"] = case_change_summary(
        case, proposals[-1] if proposals else None, decisions[-1] if decisions else None
    )
    row["why_it_here"] = case.expected
    row["title"] = case.observed
    row["proposal_count"] = len(proposals)
    return row


def _filter_by_tab(
    cases: list[Case], session: Session, actor: Actor, tab: str
) -> list[Case]:
    if tab == "needs_me":
        return cases_needing_actor(cases, session, actor)
    if tab == "all_open":
        return [c for c in cases if c.status in _OPEN_STATUSES]
    if tab == "waiting_on_client":
        return [c for c in cases if c.status == "waiting_on_client"]
    if tab == "resolved":
        return [c for c in cases if c.status in ("resolved", "cleared")]
    raise HTTPException(status_code=422, detail="unknown tab")


def _tax_effect_total(cases: list[Case]) -> dict[str, str]:
    federal = sum((c.tax_effect_federal or 0) for c in cases)
    california = sum((c.tax_effect_california or 0) for c in cases)
    return {"federal": str(federal), "california": str(california)}


@router.get("/cases")
def list_queue(
    tab: str = Query(default="needs_me"),
    actor: Actor = Depends(require_non_client),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    all_cases = list_cases(session)
    counts = {
        "needs_me": len(_filter_by_tab(all_cases, session, actor, "needs_me")),
        "all_open": len(_filter_by_tab(all_cases, session, actor, "all_open")),
        "waiting_on_client": len(
            _filter_by_tab(all_cases, session, actor, "waiting_on_client")
        ),
        "resolved": len(_filter_by_tab(all_cases, session, actor, "resolved")),
    }
    selected = _filter_by_tab(all_cases, session, actor, tab)

    groups = []
    for severity in _SEVERITY_GROUP_ORDER:
        in_group = [c for c in selected if c.severity == severity]
        if not in_group:
            continue
        groups.append(
            {
                "severity": severity,
                "count": len(in_group),
                "total_tax_effect": _tax_effect_total(in_group),
                "cases": [_case_row(session, actor, c) for c in in_group],
            }
        )
    body = {"tab": tab, "counts": counts, "groups": groups}
    return redact_for_actor(actor, packet, body)


@router.get("/cases/{case_id}")
def get_case_detail(
    case_id: str,
    actor: Actor = Depends(require_non_client),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    case = get_case(session, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="not found")
    record_last_seen(session, actor.id, "case", case_id, datetime.now(UTC))
    proposals = list_case_proposals(session, case_id)
    decisions = list_case_decisions(session, case_id)
    body = {
        **_case_row(session, actor, case),
        "proposals": [p.to_dict() for p in proposals],
        "decisions": [d.to_dict() for d in decisions],
        # Step 10: AI-suggested, shown separately from the case's own
        # verified proposals/decisions above -- no authority of its own.
        "ai_suggestions": list_case_suggestions(session, case_id),
    }
    return redact_for_actor(actor, packet, body)


@router.get("/cases/{case_id}/activity")
def get_case_activity(
    case_id: str,
    actor: Actor = Depends(require_non_client),
    session: Session = Depends(get_session),
) -> dict:
    """The event timeline for one case (docs/UX.md S2 "Activity"), newest
    first, with actor, role, time and revision."""
    packet = load_packet()
    if get_case(session, case_id) is None:
        raise HTTPException(status_code=404, detail="not found")
    actors = load_actors(packet)
    events = list_events_for_entity(session, "case", case_id)
    rows = []
    for event in reversed(events):
        known_actor = actors.get(event.actor_id) if event.actor_id else None
        is_system = event.actor_id == "system"
        rows.append(
            {
                "event_type": event.event_type,
                "actor_id": event.actor_id,
                "actor_name": known_actor.name
                if known_actor
                else ("System" if is_system else event.actor_id),
                "actor_role": known_actor.role
                if known_actor
                else ("system" if is_system else None),
                "occurred_at": event.occurred_at.isoformat()
                if event.occurred_at
                else None,
                "revision": event.revision,
                "payload": event.payload,
            }
        )
    return redact_for_actor(actor, packet, {"events": rows})


def _perform_case_action(
    session: Session,
    actor: Actor,
    action: str,
    case_id: str,
    body: RevisionedRequest,
    extra_payload: dict[str, Any] | None = None,
) -> dict:
    packet = load_packet()
    payload = {
        **body.model_dump(exclude={"expected_revision"}),
        **(extra_payload or {}),
    }
    result = perform(
        session,
        actor,
        action,
        entity_id=case_id,
        expected_revision=body.expected_revision,
        payload=payload,
        packet=packet,
    )
    return redact_for_actor(actor, packet, result.current_state.to_dict())


@router.post("/cases")
def open_case(
    body: OpenCaseRequest,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    result = perform(
        session, actor, "open_case_by_hand", payload=body.model_dump(), packet=packet
    )
    return redact_for_actor(actor, packet, result.current_state.to_dict())


@router.post("/cases/sync")
def sync(
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    result = perform(session, actor, "sync_cases", packet=packet)
    return redact_for_actor(actor, packet, result.current_state.to_dict())


@router.post("/cases/{case_id}/pick-up")
def pick_up(
    case_id: str,
    body: RevisionedRequest,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    return _perform_case_action(session, actor, "pick_up", case_id, body)


@router.post("/cases/{case_id}/ask-client")
def ask_client(
    case_id: str,
    body: AskClientRequest,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    return _perform_case_action(session, actor, "ask_client", case_id, body)


@router.post("/cases/{case_id}/client-answered")
def client_answered(
    case_id: str,
    body: ClientAnsweredRequest,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    return _perform_case_action(session, actor, "client_answered", case_id, body)


@router.post("/cases/{case_id}/submit-proposal")
def submit_proposal(
    case_id: str,
    body: SubmitProposalRequest,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    return _perform_case_action(session, actor, "submit_proposal", case_id, body)


@router.post("/cases/{case_id}/return")
def return_proposal(
    case_id: str,
    body: NoteRequest,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    return _perform_case_action(session, actor, "return", case_id, body)


@router.post("/cases/{case_id}/approve")
def approve(
    case_id: str,
    body: ApproveRequest,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    return _perform_case_action(session, actor, "approve", case_id, body)


@router.post("/cases/{case_id}/partner-approve")
def partner_approve(
    case_id: str,
    body: ApproveRequest,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    return _perform_case_action(session, actor, "partner_approve", case_id, body)


@router.post("/cases/{case_id}/partner-return")
def partner_return(
    case_id: str,
    body: NoteRequest,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    return _perform_case_action(session, actor, "partner_return", case_id, body)


@router.post("/cases/{case_id}/reopen")
def reopen(
    case_id: str,
    body: ReopenRequest,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    return _perform_case_action(session, actor, "reopen", case_id, body)


@router.post("/cases/{case_id}/reassign")
def reassign(
    case_id: str,
    body: ReassignRequest,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    return _perform_case_action(session, actor, "reassign", case_id, body)
