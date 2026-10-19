"""I5: rebuilding the current state from events gives exactly what's
stored.
"""

from collections.abc import Iterator
from decimal import Decimal

import pytest
from proofline.actions.cases import sync_cases_from_findings
from proofline.actions.service import perform
from proofline.checks.models import CheckResult, TaxEffect
from proofline.db.models import (
    Adjustment,
    Base,
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
from proofline.db.rebuild import rebuild_current_state
from proofline.packet import load_packet
from proofline.provenance.claim_identity import lot_1099b
from proofline.security.actors import Actor
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

REVIEWER = Actor(id="st-02", name="Daniel", role="reviewer", clearance=True)
PREPARER = Actor(id="st-01", name="Priya", role="preparer", clearance=True)
PARTNER = Actor(id="st-03", name="Helen", role="partner", clearance=True)
CLIENT = Actor(id="cu-01", name="Ngozi", role="client", clearance=False)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _review_note_snapshot(session: Session) -> dict[str, dict]:
    notes = session.scalars(select(ReviewNote)).all()
    return {note.id: note.to_dict() for note in notes}


def _check_run_snapshot(session: Session) -> dict[str, dict]:
    runs = session.scalars(select(CheckRun)).all()
    return {run.id: run.to_dict() for run in runs}


def _case_snapshot(session: Session) -> dict[str, dict]:
    return {
        case.case_id: case.to_dict() for case in session.scalars(select(Case)).all()
    }


def _proposal_snapshot(session: Session) -> dict[str, dict]:
    return {p.id: p.to_dict() for p in session.scalars(select(CaseProposal)).all()}


def _decision_snapshot(session: Session) -> dict[str, dict]:
    return {d.id: d.to_dict() for d in session.scalars(select(CaseDecision)).all()}


def _adjustment_snapshot(session: Session) -> dict[str, dict]:
    return {a.id: a.to_dict() for a in session.scalars(select(Adjustment)).all()}


def test_rebuild_matches_the_live_current_state(session: Session) -> None:
    packet = load_packet()

    added = perform(
        session,
        REVIEWER,
        "add_review_note",
        payload={"about_type": "document", "about_id": "D30", "body": "check this"},
    )
    note_id = added.current_state.id
    perform(
        session,
        PREPARER,
        "respond_review_note",
        entity_id=note_id,
        expected_revision=1,
        payload={"body": "responding"},
    )
    perform(
        session,
        PARTNER,
        "resolve_review_note",
        entity_id=note_id,
        expected_revision=2,
        payload={"resolution": "fixed"},
    )
    perform(session, REVIEWER, "record_check_run", packet=packet)
    perform(
        session,
        REVIEWER,
        "reveal_sensitive_value",
        entity_id="household:theo",
        payload={"field": "ssn", "reason": "confirming for the client's call"},
    )
    session.flush()

    live_notes = _review_note_snapshot(session)
    live_check_runs = _check_run_snapshot(session)
    events_before = len(session.scalars(select(Event)).all())

    rebuild_current_state(session)
    session.flush()

    assert _review_note_snapshot(session) == live_notes
    assert _check_run_snapshot(session) == live_check_runs
    # Rebuilding never touches events themselves.
    assert len(session.scalars(select(Event)).all()) == events_before


def test_rebuild_matches_a_full_case_lifecycle(session: Session) -> None:
    """Exercises every registered case rebuild handler: opened (from a
    finding), picked up, a proposal submitted, returned, resubmitted,
    approved to awaiting_partner (tax effect over 1,000), partner-approved,
    reopened, and reassigned -- then confirms a from-scratch replay matches
    the live current state for cases, proposals and decisions alike."""
    finding = CheckResult(
        check_id="TEST_REBUILD_CHECK",
        check_version=1,
        area="investments",
        scope="transaction",
        finding_type="error",
        severity="tax_amount",
        evidence_refs=["ev-0001"],
        claims=[lot_1099b("Test Issuer", "N1")],
        observed="observed",
        expected="expected",
        tax_effect=TaxEffect(
            federal=Decimal("15536.00"),
            california=Decimal("1619.00"),
            kind="estimate",
            direction="overstated",
        ),
        limitations="none",
        recommended_action="fix it",
    )
    (case,) = sync_cases_from_findings(session, [finding])
    case = perform(
        session,
        PREPARER,
        "pick_up",
        entity_id=case.case_id,
        expected_revision=case.revision,
    ).current_state
    case = perform(
        session,
        PREPARER,
        "submit_proposal",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={
            "resolution_type": "adjust_number",
            "fields": {
                "adjustments": [{"claim": "x", "old_value": "0", "new_value": "100"}]
            },
            "evidence_refs": ["ev-0001"],
        },
    ).current_state
    case = perform(
        session,
        REVIEWER,
        "return",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={"note": "need more support"},
    ).current_state
    case = perform(
        session,
        PREPARER,
        "submit_proposal",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={
            "resolution_type": "adjust_number",
            "fields": {
                "adjustments": [{"claim": "x", "old_value": "0", "new_value": "100"}]
            },
            "evidence_refs": ["ev-0001", "D11"],
        },
    ).current_state
    case = perform(
        session,
        REVIEWER,
        "approve",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={"note": "looks right"},
    ).current_state
    assert case.status == "awaiting_partner"
    case = perform(
        session,
        PARTNER,
        "partner_approve",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={},
    ).current_state
    case = perform(
        session,
        REVIEWER,
        "reopen",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={"reason": "an approved input changed"},
    ).current_state
    perform(
        session,
        REVIEWER,
        "reassign",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={"assignee_id": "st-10"},
    )
    session.flush()

    live_cases = _case_snapshot(session)
    live_proposals = _proposal_snapshot(session)
    live_decisions = _decision_snapshot(session)
    live_adjustments = _adjustment_snapshot(session)
    assert len(live_adjustments) == 1, (
        "partner_approve should have created one Adjustment"
    )

    rebuild_current_state(session)
    session.flush()

    assert _adjustment_snapshot(session) == live_adjustments
    assert _case_snapshot(session) == live_cases
    assert _proposal_snapshot(session) == live_proposals
    assert _decision_snapshot(session) == live_decisions


def _sign_off_snapshot(session: Session) -> dict[str, dict]:
    return {s.id: s.to_dict() for s in session.scalars(select(SignOff)).all()}


def _disposition_snapshot(session: Session) -> dict[str, dict]:
    return {
        d.document_id: d.to_dict()
        for d in session.scalars(select(DocumentDisposition)).all()
    }


def _verification_snapshot(session: Session) -> dict[str, dict]:
    return {
        v.claim_key: v.to_dict()
        for v in session.scalars(select(ClaimVerification)).all()
    }


def test_rebuild_matches_step_7_sign_off_disposition_and_bulk_verify(
    session: Session,
) -> None:
    """Exercises every registered Step 7 rebuild handler: sign-off at v1,
    carry-over confirmed (log-only, no current-state row to check),
    sign-off at v2, a document disposition confirmed, a bulk verify, then
    an undo -- then confirms a from-scratch replay matches the live
    current state for sign-offs, dispositions and claim verifications."""
    packet = load_packet()

    perform(
        session,
        REVIEWER,
        "sign_off",
        payload={"scope": "investments", "version": "v1"},
        packet=packet,
    )
    perform(
        session,
        REVIEWER,
        "confirm_carryover",
        payload={
            "scope": "investments",
            "old_document_id": "D30",
            "new_document_id": "D31",
        },
        packet=packet,
    )
    perform(
        session,
        REVIEWER,
        "sign_off",
        payload={"scope": "investments", "version": "v2"},
        packet=packet,
    )
    perform(
        session,
        PREPARER,
        "confirm_disposition",
        entity_id="D10",
        expected_revision=1,
        payload={"disposition": "duplicate_of", "reason": "same as D09"},
        packet=packet,
    )
    bulk_result = perform(
        session,
        PREPARER,
        "bulk_verify",
        payload={"claim_keys": ["1099b_lot:Northlake Securities:N1"]},
        packet=packet,
    )
    perform(
        session,
        PREPARER,
        "undo_bulk_verify",
        payload={"event_id": str(bulk_result.event.id)},
        packet=packet,
    )
    perform(
        session,
        PREPARER,
        "bulk_verify",
        payload={"claim_keys": ["1099b_lot:Northlake Securities:N2"]},
        packet=packet,
    )
    session.flush()

    live_sign_offs = _sign_off_snapshot(session)
    live_dispositions = _disposition_snapshot(session)
    live_verifications = _verification_snapshot(session)
    assert len(live_sign_offs) == 2
    assert len(live_dispositions) == 1
    assert len(live_verifications) == 1

    rebuild_current_state(session)
    session.flush()

    assert _sign_off_snapshot(session) == live_sign_offs
    assert _disposition_snapshot(session) == live_dispositions
    assert _verification_snapshot(session) == live_verifications


def test_rebuild_is_idempotent(session: Session) -> None:
    perform(
        session,
        REVIEWER,
        "add_review_note",
        payload={"about_type": "document", "about_id": "D30", "body": "x"},
    )
    session.flush()

    rebuild_current_state(session)
    session.flush()
    first = _review_note_snapshot(session)

    rebuild_current_state(session)
    session.flush()
    second = _review_note_snapshot(session)

    assert first == second


def _filed_record_snapshot(session: Session) -> dict[str, dict]:
    return {r.id: r.to_dict() for r in session.scalars(select(FiledRecord)).all()}


def test_rebuild_matches_filing_authorization_and_submission(session: Session) -> None:
    """Exercises the Step 8 rebuild handler: a rejected submission writes
    no `FiledRecord` (I6: written once, only on acceptance), an accepted
    one does -- then confirms a from-scratch replay matches the live
    `filed_records` table exactly, using the id the event itself carries
    (not one rebuild would have to invent)."""
    packet = load_packet()
    auth = perform(
        session,
        CLIENT,
        "authorize_filing",
        payload={"pins": {"taxpayer": "41207", "spouse": "88310"}},
        packet=packet,
    )
    package_reference = auth.current_state["package_reference"]

    perform(
        session,
        REVIEWER,
        "submit_filing",
        payload={
            "jurisdiction": "federal",
            "package_reference": package_reference,
            "status": "rejected",
            "codes": [{"code": "R0000-504-02", "message": "mismatch"}],
        },
        packet=packet,
    )
    perform(
        session,
        REVIEWER,
        "submit_filing",
        payload={
            "jurisdiction": "federal",
            "package_reference": package_reference,
            "status": "accepted",
            "codes": [],
        },
        packet=packet,
    )
    perform(
        session,
        REVIEWER,
        "submit_filing",
        payload={
            "jurisdiction": "california",
            "package_reference": package_reference,
            "status": "accepted",
            "codes": [],
        },
        packet=packet,
    )
    session.flush()

    live_records = _filed_record_snapshot(session)
    assert len(live_records) == 2

    rebuild_current_state(session)
    session.flush()

    assert _filed_record_snapshot(session) == live_records


def test_rebuild_skips_events_with_no_registered_handler(session: Session) -> None:
    """An old Step 1 "test_event" row (or any event type rebuild doesn't
    know how to replay) is read and skipped, not an error."""
    from proofline.db.repository import insert_event

    insert_event(session, "test_event", {"foo": "bar"})
    session.flush()

    rebuild_current_state(session)  # must not raise
