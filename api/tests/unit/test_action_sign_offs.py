"""C2 sign-off and carry-over confirmation, through `perform()`, against
the real packet's D30/D31 scenario (docs/CONTRACTS.md C2, A2).
"""

import datetime as dt
from collections.abc import Iterator

import pytest
from proofline.actions.errors import ActionConflict, ActionValidationError
from proofline.actions.service import perform
from proofline.actions.sign_offs import resolved_decision_ids_in_scope
from proofline.analysis.calculation import line_claim_identity
from proofline.db.models import Adjustment, Base, Case, CaseDecision, CaseProposal
from proofline.db.repository import (
    get_latest_sign_off,
    insert_adjustment,
    insert_case,
    insert_case_decision,
    insert_case_proposal,
    list_sign_offs,
)
from proofline.packet import load_packet
from proofline.security.actors import Actor
from proofline.security.permissions import PermissionDenied
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

PREPARER = Actor(id="st-01", name="Priya", role="preparer", clearance=True)
REVIEWER = Actor(id="st-02", name="Daniel", role="reviewer", clearance=True)
PARTNER = Actor(id="st-03", name="Helen", role="partner", clearance=True)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_sign_off_requires_a_reviewer_role(session: Session) -> None:
    packet = load_packet()
    with pytest.raises(PermissionDenied):
        perform(
            session,
            PREPARER,
            "sign_off",
            payload={"scope": "business"},
            packet=packet,
        )


def test_sign_off_tax_computation_requires_the_partner(session: Session) -> None:
    packet = load_packet()
    with pytest.raises(PermissionDenied):
        perform(
            session,
            REVIEWER,
            "sign_off",
            payload={"scope": "tax_computation"},
            packet=packet,
        )


def test_sign_off_a_clean_scope_records_version_1(session: Session) -> None:
    packet = load_packet()
    result = perform(
        session,
        REVIEWER,
        "sign_off",
        payload={"scope": "business", "version": "v1"},
        packet=packet,
    )
    row = result.current_state
    assert row.scope == "business"
    assert row.version == 1
    assert row.signed_by == REVIEWER.id
    assert row.engine_version == "v1"


def test_resolved_decision_ids_in_scope_only_counts_approve_and_partner_approve(
    session: Session,
) -> None:
    case = Case(
        case_id="case-1",
        root_cause_key="rck-1",
        origin="check",
        scope="business",
        claims=[],
        severity="tax_amount",
        status="resolved",
        revision=1,
        evidence_refs=[],
        observed="x",
        expected="y",
    )
    insert_case(session, case)
    when = dt.datetime.now(dt.UTC)
    insert_case_decision(
        session,
        CaseDecision(
            id="decision-return",
            case_id="case-1",
            proposal_revision=1,
            decision="return",
            decided_by=REVIEWER.id,
            decided_at=when,
        ),
    )
    insert_case_decision(
        session,
        CaseDecision(
            id="decision-approve",
            case_id="case-1",
            proposal_revision=2,
            decision="approve",
            decided_by=REVIEWER.id,
            decided_at=when,
        ),
    )
    assert resolved_decision_ids_in_scope(session, "business") == ["decision-approve"]
    assert resolved_decision_ids_in_scope(session, "investments") == []


def test_signing_off_again_after_a_new_decision_changes_the_decisions_fingerprint(
    session: Session,
) -> None:
    """Regression test: `compute_fingerprints`'s `decisions` component used
    to be computed with no real decision ids at every call site, so it was
    always the same empty hash -- CONTRACTS.md C2's "a decision changed ->
    change pending" could never be detected. `sign_off` now threads real
    resolved decisions through (`resolved_decision_ids_in_scope`)."""
    packet = load_packet()
    first = perform(
        session,
        REVIEWER,
        "sign_off",
        payload={"scope": "business", "version": "v1"},
        packet=packet,
    ).current_state

    case = Case(
        case_id="case-2",
        root_cause_key="rck-2",
        origin="check",
        scope="business",
        claims=[],
        severity="tax_amount",
        status="resolved",
        revision=1,
        evidence_refs=[],
        observed="x",
        expected="y",
    )
    insert_case(session, case)
    insert_case_decision(
        session,
        CaseDecision(
            id="decision-1",
            case_id="case-2",
            proposal_revision=1,
            decision="approve",
            decided_by=REVIEWER.id,
            decided_at=dt.datetime.now(dt.UTC),
        ),
    )

    second = perform(
        session,
        REVIEWER,
        "sign_off",
        payload={"scope": "business", "version": "v1"},
        packet=packet,
    ).current_state

    assert second.version == 2
    assert first.decisions_fingerprint != second.decisions_fingerprint


def test_sign_off_blocks_the_signer_s_own_adjustment_in_scope(session: Session) -> None:
    packet = load_packet()
    rv = packet.return_versions[-1]
    claim_key = next(
        str(claim)
        for line in rv.lines
        if (claim := line_claim_identity(packet, line)) is not None
    )

    case = Case(
        case_id="case-1",
        root_cause_key="rck-1",
        origin="check",
        scope="investments",
        claims=[claim_key],
        severity="tax_amount",
        status="resolved",
        revision=1,
        evidence_refs=[],
        observed="x",
        expected="y",
    )
    insert_case(session, case)
    insert_adjustment(
        session,
        Adjustment(
            id="adj-1",
            claim_key=claim_key,
            old_value="1",
            new_value="2",
            evidence_refs=[],
            case_id="case-1",
        ),
    )
    insert_case_proposal(
        session,
        CaseProposal(
            id="proposal-1",
            case_id="case-1",
            revision_number=1,
            resolution_type="adjust_number",
            fields={},
            evidence_refs=[],
            proposed_by=REVIEWER.id,
            proposed_at=dt.datetime.now(dt.UTC),
        ),
    )

    with pytest.raises(ActionConflict, match="own adjustment"):
        perform(
            session,
            REVIEWER,
            "sign_off",
            payload={"scope": "investments", "version": "v1"},
            packet=packet,
        )


def test_investments_signed_at_v1_then_v2_needs_carryover_confirmation_first(
    session: Session,
) -> None:
    packet = load_packet()
    perform(
        session,
        REVIEWER,
        "sign_off",
        payload={"scope": "investments", "version": "v1"},
        packet=packet,
    )

    with pytest.raises(ActionConflict, match="confirm the carry-over"):
        perform(
            session,
            REVIEWER,
            "sign_off",
            payload={"scope": "investments", "version": "v2"},
            packet=packet,
        )


def test_confirm_carryover_then_sign_off_v2_creates_version_2_keeping_version_1(
    session: Session,
) -> None:
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
    result = perform(
        session,
        REVIEWER,
        "sign_off",
        payload={"scope": "investments", "version": "v2"},
        packet=packet,
    )

    assert result.current_state.version == 2
    assert result.current_state.engine_version == "v2"
    sign_offs = list_sign_offs(session, "investments")
    assert [s.version for s in sign_offs] == [1, 2]
    assert sign_offs[0].engine_version == "v1"
    latest = get_latest_sign_off(session, "investments")
    assert latest.version == 2


def test_confirm_carryover_requires_a_reviewer_role(session: Session) -> None:
    packet = load_packet()
    with pytest.raises(PermissionDenied):
        perform(
            session,
            PREPARER,
            "confirm_carryover",
            payload={
                "scope": "investments",
                "old_document_id": "D30",
                "new_document_id": "D31",
            },
            packet=packet,
        )


def test_confirm_carryover_rejects_a_document_that_was_not_actually_replaced(
    session: Session,
) -> None:
    """Regression test: `confirm_carryover` used to take `old_document_id`/
    `new_document_id` straight from the caller with no cross-check against
    the packet's real, resolver-found replacement -- a wrong or made-up
    pair would confirm just as successfully as the real one, letting a
    scope re-sign as if a genuine carry-over had been verified when it
    hadn't. Caught by the reviewer agent."""
    packet = load_packet()
    perform(
        session,
        REVIEWER,
        "sign_off",
        payload={"scope": "investments", "version": "v1"},
        packet=packet,
    )
    with pytest.raises(
        ActionValidationError, match="not a pending document replacement"
    ):
        perform(
            session,
            REVIEWER,
            "confirm_carryover",
            payload={
                "scope": "investments",
                "old_document_id": "D08",  # a real document, never replaced
                "new_document_id": "D31",
            },
            packet=packet,
        )


def test_confirm_carryover_rejects_the_wrong_new_document(session: Session) -> None:
    packet = load_packet()
    perform(
        session,
        REVIEWER,
        "sign_off",
        payload={"scope": "investments", "version": "v1"},
        packet=packet,
    )
    with pytest.raises(ActionValidationError, match="was replaced by"):
        perform(
            session,
            REVIEWER,
            "confirm_carryover",
            payload={
                "scope": "investments",
                "old_document_id": "D30",
                "new_document_id": "D08",  # D30 was really replaced by D31
            },
            packet=packet,
        )


def test_confirm_carryover_requires_a_prior_sign_off(session: Session) -> None:
    packet = load_packet()
    with pytest.raises(ActionValidationError, match="never been signed off"):
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


def test_sign_off_without_a_scope_is_a_validation_error(session: Session) -> None:
    packet = load_packet()
    with pytest.raises(ActionValidationError):
        perform(session, REVIEWER, "sign_off", payload={}, packet=packet)
