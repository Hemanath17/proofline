"""One test per row of the C1 transition table (docs/CONTRACTS.md), plus
root-cause grouping/clearing and the resolution-type evidence rules.
"""

from collections.abc import Iterator
from decimal import Decimal

import pytest
from proofline.actions.cases import sync_cases_from_findings, validate_resolution_fields
from proofline.actions.errors import ActionConflict, ActionValidationError
from proofline.actions.service import perform
from proofline.checks.models import CheckResult, TaxEffect
from proofline.db.models import Base, Case
from proofline.db.repository import get_case, insert_case, list_case_proposals
from proofline.provenance.claim_identity import lot_1099b
from proofline.security.actors import Actor
from proofline.security.permissions import PermissionDenied
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

PREPARER = Actor(id="st-01", name="Priya", role="preparer", clearance=True)
PREPARER_2 = Actor(id="st-10", name="Other Preparer", role="preparer", clearance=True)
REVIEWER = Actor(id="st-02", name="Daniel", role="reviewer", clearance=True)
PARTNER = Actor(id="st-03", name="Helen", role="partner", clearance=True)
CLIENT = Actor(id="cu-01", name="Ngozi", role="client", clearance=False)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _make_finding(
    check_id: str = "TEST_CHECK",
    claim_key: str = "x",
    federal: Decimal = Decimal("50.00"),
) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        check_version=1,
        area="investments",
        scope="transaction",
        finding_type="error",
        severity="tax_amount",
        evidence_refs=["ev-0001"],
        claims=[lot_1099b("Test Issuer", claim_key)],
        observed="observed sentence",
        expected="expected sentence",
        tax_effect=TaxEffect(
            federal=federal,
            california=Decimal("5.00"),
            kind="estimate",
            direction="overstated",
        ),
        limitations="none",
        recommended_action="fix it",
    )


def _tax_case(
    session: Session, federal: Decimal, california: Decimal = Decimal(0)
) -> Case:
    case = Case(
        case_id=f"case-tax-{federal}-{id(session)}",
        root_cause_key=f"rck-{federal}-{id(session)}",
        origin="check",
        scope="investments",
        claims=[],
        severity="tax_amount",
        status="open",
        revision=1,
        evidence_refs=[],
        observed="o",
        expected="e",
        tax_effect_federal=federal,
        tax_effect_california=california,
        tax_effect_kind="estimate",
        tax_effect_direction="overstated",
        impact_unknown=False,
    )
    insert_case(session, case)
    return case


def _investigating_case(session: Session, **kwargs) -> Case:
    case = _tax_case(session, **kwargs) if kwargs else _tax_case(session, Decimal(50))
    return perform(
        session,
        PREPARER,
        "pick_up",
        entity_id=case.case_id,
        expected_revision=case.revision,
    ).current_state


def _in_review_case(session: Session, proposer: Actor = PREPARER, **tax_kwargs) -> Case:
    case = _investigating_case(session, **tax_kwargs)
    return perform(
        session,
        proposer,
        "submit_proposal",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={
            "resolution_type": "mark_legitimate",
            "fields": {"reason": "expected variance"},
            "evidence_refs": ["ev-0001"],
        },
    ).current_state


def _in_review_case_proposed_by(
    session: Session, proposed_by: str, **tax_kwargs
) -> Case:
    """Like `_in_review_case`, but inserts the `CaseProposal` directly with
    an arbitrary `proposed_by`, bypassing `submit_proposal`'s own
    preparer-only permission check -- used only to test the independent
    "nobody reviews their own work" guard inside `return`/`approve`
    themselves, for a hypothetical where the proposer and the reviewer
    turn out to be the same actor."""
    from proofline.db.models import CaseProposal
    from proofline.db.repository import apply_revision_cas, insert_case_proposal

    case = _investigating_case(session, **tax_kwargs)
    insert_case_proposal(
        session,
        CaseProposal(
            id=f"proposal-test-{case.case_id}",
            case_id=case.case_id,
            revision_number=1,
            resolution_type="mark_legitimate",
            fields={"reason": "expected variance"},
            evidence_refs=["ev-0001"],
            proposed_by=proposed_by,
            proposed_at=case.updated_at,
        ),
    )
    return apply_revision_cas(
        session, Case, case.case_id, case.revision, {"status": "in_review"}
    )


# -- Root-cause grouping and clearing ------------------------------------


def test_sync_cases_from_findings_opens_one_case_per_root_cause(
    session: Session,
) -> None:
    finding_a = _make_finding(claim_key="a")
    finding_b = _make_finding(claim_key="b")
    touched = sync_cases_from_findings(session, [finding_a, finding_b])
    assert len(touched) == 2
    assert len({c.root_cause_key for c in touched}) == 2


def test_sync_cases_from_findings_does_not_duplicate_on_rerun(session: Session) -> None:
    finding = _make_finding()
    sync_cases_from_findings(session, [finding])
    touched_again = sync_cases_from_findings(session, [finding])
    assert len(touched_again) == 1
    assert touched_again[0].status == "open"


def test_sync_cases_from_findings_groups_same_root_cause_across_claims(
    session: Session,
) -> None:
    """Two findings for the same check + same claims (e.g. a rerun that
    bundles multiple disagreeing sources into one finding, or two findings
    that happen to share every claim) collapse to one case."""
    finding = _make_finding(claim_key="shared")
    finding_same_claims = _make_finding(claim_key="shared")
    touched = sync_cases_from_findings(session, [finding, finding_same_claims])
    assert len({c.case_id for c in touched}) == 1


def test_sync_cases_clears_case_when_finding_stops_firing(session: Session) -> None:
    finding = _make_finding()
    sync_cases_from_findings(session, [finding])
    touched = sync_cases_from_findings(session, [])
    assert len(touched) == 1
    assert touched[0].status == "cleared"
    assert touched[0].cleared_reason == "the finding stopped firing"


def test_sync_cases_does_not_clear_a_case_already_in_review(session: Session) -> None:
    finding = _make_finding()
    (case,) = sync_cases_from_findings(session, [finding])
    case = perform(
        session,
        PREPARER,
        "pick_up",
        entity_id=case.case_id,
        expected_revision=case.revision,
    ).current_state
    proposal_result = perform(
        session,
        PREPARER,
        "submit_proposal",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={
            "resolution_type": "mark_legitimate",
            "fields": {"reason": "x"},
            "evidence_refs": ["ev-0001"],
        },
    )
    assert proposal_result.current_state.status == "in_review"

    sync_cases_from_findings(session, [])

    assert get_case(session, case.case_id).status == "in_review"


# -- open_case_by_hand ----------------------------------------------------


def test_open_case_by_hand_creates_an_open_case(session: Session) -> None:
    result = perform(
        session,
        PREPARER,
        "open_case_by_hand",
        payload={
            "origin": "document",
            "origin_ref": "D99",
            "scope": "business",
            "severity": "info",
            "observed": "something odd",
            "expected": "should agree",
        },
    )
    assert result.current_state.status == "open"
    assert result.current_state.origin == "document"


def test_open_case_by_hand_duplicate_origin_ref_conflicts(session: Session) -> None:
    payload = {
        "origin": "document",
        "origin_ref": "D99",
        "scope": "business",
        "severity": "info",
        "observed": "x",
        "expected": "y",
    }
    perform(session, PREPARER, "open_case_by_hand", payload=payload)
    with pytest.raises(ActionConflict):
        perform(session, PREPARER, "open_case_by_hand", payload=payload)


def test_open_case_by_hand_denied_for_client(session: Session) -> None:
    with pytest.raises(PermissionDenied):
        perform(
            session,
            CLIENT,
            "open_case_by_hand",
            payload={
                "origin": "client",
                "origin_ref": "qa-01",
                "scope": "business",
                "severity": "info",
                "observed": "x",
                "expected": "y",
            },
        )


# -- pick_up: open -> investigating, preparer only. ----------------------


def test_pick_up_moves_open_case_to_investigating(session: Session) -> None:
    case = _tax_case(session, Decimal(1))
    result = perform(
        session,
        PREPARER,
        "pick_up",
        entity_id=case.case_id,
        expected_revision=case.revision,
    )
    assert result.current_state.status == "investigating"
    assert result.current_state.assignee_id == PREPARER.id


def test_pick_up_denied_for_reviewer(session: Session) -> None:
    case = _tax_case(session, Decimal(1))
    with pytest.raises(PermissionDenied):
        perform(
            session,
            REVIEWER,
            "pick_up",
            entity_id=case.case_id,
            expected_revision=case.revision,
        )


def test_pick_up_on_non_open_case_conflicts(session: Session) -> None:
    case = _investigating_case(session)
    with pytest.raises(ActionConflict):
        perform(
            session,
            PREPARER,
            "pick_up",
            entity_id=case.case_id,
            expected_revision=case.revision,
        )


# -- ask_client: investigating -> waiting_on_client, preparer, needs a
# specific question. -------------------------------------------------------


def test_ask_client_requires_a_question(session: Session) -> None:
    case = _investigating_case(session)
    with pytest.raises(ActionValidationError):
        perform(
            session,
            PREPARER,
            "ask_client",
            entity_id=case.case_id,
            expected_revision=case.revision,
            payload={},
        )


def test_ask_client_moves_to_waiting_on_client(session: Session) -> None:
    case = _investigating_case(session)
    result = perform(
        session,
        PREPARER,
        "ask_client",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={"question": "Can you confirm the SSN on file?"},
    )
    assert result.current_state.status == "waiting_on_client"


# -- client_answered: waiting_on_client -> investigating, client or
# system, saved as evidence. ----------------------------------------------


def test_client_answered_requires_evidence_ref(session: Session) -> None:
    case = _investigating_case(session)
    case = perform(
        session,
        PREPARER,
        "ask_client",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={"question": "q"},
    ).current_state
    with pytest.raises(ActionValidationError):
        perform(
            session,
            CLIENT,
            "client_answered",
            entity_id=case.case_id,
            expected_revision=case.revision,
            payload={},
        )


def test_client_answered_saves_evidence_and_returns_to_investigating(
    session: Session,
) -> None:
    case = _investigating_case(session)
    case = perform(
        session,
        PREPARER,
        "ask_client",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={"question": "q"},
    ).current_state
    result = perform(
        session,
        CLIENT,
        "client_answered",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={"evidence_ref": "msg-10"},
    )
    assert result.current_state.status == "investigating"
    assert "msg-10" in result.current_state.evidence_refs


def test_client_answered_denied_for_a_preparer(session: Session) -> None:
    case = _investigating_case(session)
    case = perform(
        session,
        PREPARER,
        "ask_client",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={"question": "q"},
    ).current_state
    with pytest.raises(PermissionDenied):
        perform(
            session,
            PREPARER,
            "client_answered",
            entity_id=case.case_id,
            expected_revision=case.revision,
            payload={"evidence_ref": "msg-10"},
        )


# -- submit_proposal: investigating -> in_review, preparer, evidence per
# resolution type. --------------------------------------------------------


@pytest.mark.parametrize(
    "resolution_type,fields",
    [
        ("resolve_evidence_conflict", {"evidence_a": "D01", "evidence_b": "D02"}),
        ("record_judgment", {"reasoning": "x"}),
        ("adjust_number", {"adjustments": [{"claim": "x"}]}),
        ("mark_legitimate", {}),
    ],
)
def test_validate_resolution_fields_rejects_incomplete_fields(
    resolution_type: str, fields: dict
) -> None:
    with pytest.raises(ActionValidationError):
        validate_resolution_fields(resolution_type, fields)


def test_validate_resolution_fields_accepts_complete_fields() -> None:
    validate_resolution_fields(
        "resolve_evidence_conflict",
        {
            "evidence_a": "D01",
            "evidence_b": "D02",
            "chosen": "a",
            "reason": "more reliable",
        },
    )


def test_submit_proposal_requires_evidence_for_adjust_number(session: Session) -> None:
    case = _investigating_case(session)
    with pytest.raises(ActionValidationError):
        perform(
            session,
            PREPARER,
            "submit_proposal",
            entity_id=case.case_id,
            expected_revision=case.revision,
            payload={
                "resolution_type": "adjust_number",
                "fields": {
                    "adjustments": [
                        {"claim": "x", "old_value": "0", "new_value": "100"}
                    ]
                },
                "evidence_refs": [],
            },
        )


def test_submit_proposal_judgment_does_not_require_evidence_refs(
    session: Session,
) -> None:
    case = _investigating_case(session)
    result = perform(
        session,
        PREPARER,
        "submit_proposal",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={
            "resolution_type": "record_judgment",
            "fields": {
                "reasoning": "the facts support this",
                "authority": "IRC 61",
                "approved_by": "st-02",
            },
            "evidence_refs": [],
        },
    )
    assert result.current_state.status == "in_review"


def test_submit_proposal_flags_client_made_evidence(session: Session) -> None:
    case = _investigating_case(session)
    perform(
        session,
        PREPARER,
        "submit_proposal",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={
            "resolution_type": "resolve_evidence_conflict",
            "fields": {
                "evidence_a": "msg-10",
                "evidence_b": "D71",
                "chosen": "a",
                "reason": "client confirmed",
            },
            "evidence_refs": ["msg-10"],
        },
    )
    proposal = list_case_proposals(session, case.case_id)[-1]
    assert proposal.fields["client_evidence_flagged"] is True


def test_submit_proposal_denied_while_waiting_on_client(session: Session) -> None:
    case = _investigating_case(session)
    case = perform(
        session,
        PREPARER,
        "ask_client",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={"question": "q"},
    ).current_state
    with pytest.raises(ActionConflict):
        perform(
            session,
            PREPARER,
            "submit_proposal",
            entity_id=case.case_id,
            expected_revision=case.revision,
            payload={
                "resolution_type": "mark_legitimate",
                "fields": {"reason": "x"},
                "evidence_refs": ["ev-1"],
            },
        )


# -- return: in_review -> investigating, a reviewer who didn't propose,
# needs a note. ------------------------------------------------------------


def test_return_requires_a_note(session: Session) -> None:
    case = _in_review_case(session)
    with pytest.raises(ActionValidationError):
        perform(
            session,
            REVIEWER,
            "return",
            entity_id=case.case_id,
            expected_revision=case.revision,
            payload={},
        )


def test_return_moves_case_back_to_investigating(session: Session) -> None:
    case = _in_review_case(session)
    result = perform(
        session,
        REVIEWER,
        "return",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={"note": "need more evidence"},
    )
    assert result.current_state.status == "investigating"


def test_return_denied_for_the_proposer_nobody_reviews_own_work(
    session: Session,
) -> None:
    case = _in_review_case_proposed_by(session, REVIEWER.id)
    with pytest.raises(ActionConflict, match="Nobody reviews their own work"):
        perform(
            session,
            REVIEWER,
            "return",
            entity_id=case.case_id,
            expected_revision=case.revision,
            payload={"note": "x"},
        )


def test_return_denied_for_preparer_role(session: Session) -> None:
    case = _in_review_case(session)
    with pytest.raises(PermissionDenied):
        perform(
            session,
            PREPARER_2,
            "return",
            entity_id=case.case_id,
            expected_revision=case.revision,
            payload={"note": "x"},
        )


# -- approve: in_review -> resolved (<=1000) or awaiting_partner (>1000). --


def test_approve_resolves_case_under_threshold(session: Session) -> None:
    case = _in_review_case(session, federal=Decimal(500))
    result = perform(
        session,
        REVIEWER,
        "approve",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={},
    )
    assert result.current_state.status == "resolved"


def test_approve_sends_case_to_awaiting_partner_over_threshold(
    session: Session,
) -> None:
    case = _in_review_case(session, federal=Decimal(15536))
    result = perform(
        session,
        REVIEWER,
        "approve",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={},
    )
    assert result.current_state.status == "awaiting_partner"


def test_approve_at_exactly_the_threshold_resolves(session: Session) -> None:
    """The rule is "over 1,000" (`>`), not "1,000 or more" -- exactly
    1,000 must resolve directly, not go to the partner."""
    case = _in_review_case(session, federal=Decimal("1000.00"))
    result = perform(
        session,
        REVIEWER,
        "approve",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={},
    )
    assert result.current_state.status == "resolved"


def test_approve_one_cent_over_the_threshold_goes_to_the_partner(
    session: Session,
) -> None:
    case = _in_review_case(session, federal=Decimal("1000.01"))
    result = perform(
        session,
        REVIEWER,
        "approve",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={},
    )
    assert result.current_state.status == "awaiting_partner"


def test_approve_over_threshold_on_california_side_too(session: Session) -> None:
    case = _in_review_case(session, federal=Decimal(10), california=Decimal(1500))
    result = perform(
        session,
        REVIEWER,
        "approve",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={},
    )
    assert result.current_state.status == "awaiting_partner"


def test_approve_denied_for_the_proposer(session: Session) -> None:
    case = _in_review_case_proposed_by(session, REVIEWER.id, federal=Decimal(1))
    with pytest.raises(ActionConflict):
        perform(
            session,
            REVIEWER,
            "approve",
            entity_id=case.case_id,
            expected_revision=case.revision,
            payload={},
        )


# -- partner_approve / partner_return: awaiting_partner, partner only. ---


def _awaiting_partner_case(session: Session) -> Case:
    case = _in_review_case(session, federal=Decimal(15536))
    return perform(
        session,
        REVIEWER,
        "approve",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={},
    ).current_state


def test_partner_approve_resolves_the_case(session: Session) -> None:
    case = _awaiting_partner_case(session)
    result = perform(
        session,
        PARTNER,
        "partner_approve",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={},
    )
    assert result.current_state.status == "resolved"


def test_partner_approve_denied_for_reviewer(session: Session) -> None:
    case = _awaiting_partner_case(session)
    with pytest.raises(PermissionDenied):
        perform(
            session,
            REVIEWER,
            "partner_approve",
            entity_id=case.case_id,
            expected_revision=case.revision,
            payload={},
        )


def test_partner_return_requires_a_note(session: Session) -> None:
    case = _awaiting_partner_case(session)
    with pytest.raises(ActionValidationError):
        perform(
            session,
            PARTNER,
            "partner_return",
            entity_id=case.case_id,
            expected_revision=case.revision,
            payload={},
        )


def test_partner_return_moves_case_to_investigating(session: Session) -> None:
    case = _awaiting_partner_case(session)
    result = perform(
        session,
        PARTNER,
        "partner_return",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={"note": "not enough support"},
    )
    assert result.current_state.status == "investigating"


# -- reopen: resolved -> investigating, system or reviewer. --------------


def _resolved_case(session: Session) -> Case:
    case = _in_review_case(session, federal=Decimal(1))
    return perform(
        session,
        REVIEWER,
        "approve",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={},
    ).current_state


def test_reopen_requires_a_reason(session: Session) -> None:
    case = _resolved_case(session)
    with pytest.raises(ActionValidationError):
        perform(
            session,
            REVIEWER,
            "reopen",
            entity_id=case.case_id,
            expected_revision=case.revision,
            payload={},
        )


def test_reopen_moves_resolved_case_to_investigating(session: Session) -> None:
    case = _resolved_case(session)
    result = perform(
        session,
        REVIEWER,
        "reopen",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={"reason": "an approved input changed"},
    )
    assert result.current_state.status == "investigating"


def test_reopen_denied_for_preparer(session: Session) -> None:
    case = _resolved_case(session)
    with pytest.raises(PermissionDenied):
        perform(
            session,
            PREPARER,
            "reopen",
            entity_id=case.case_id,
            expected_revision=case.revision,
            payload={"reason": "x"},
        )


def test_reopen_denied_on_a_case_that_is_not_resolved(session: Session) -> None:
    case = _investigating_case(session)
    with pytest.raises(ActionConflict):
        perform(
            session,
            REVIEWER,
            "reopen",
            entity_id=case.case_id,
            expected_revision=case.revision,
            payload={"reason": "x"},
        )


# -- reassign: any open state, preparer/reviewer/admin. -------------------


def test_reassign_changes_assignee_and_keeps_status(session: Session) -> None:
    case = _investigating_case(session)
    result = perform(
        session,
        REVIEWER,
        "reassign",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={"assignee_id": "st-10"},
    )
    assert result.current_state.assignee_id == "st-10"
    assert result.current_state.status == "investigating"


def test_reassign_denied_on_resolved_case(session: Session) -> None:
    case = _resolved_case(session)
    with pytest.raises(ActionConflict):
        perform(
            session,
            REVIEWER,
            "reassign",
            entity_id=case.case_id,
            expected_revision=case.revision,
            payload={"assignee_id": "st-10"},
        )


def test_reassign_denied_for_client(session: Session) -> None:
    case = _investigating_case(session)
    with pytest.raises(PermissionDenied):
        perform(
            session,
            CLIENT,
            "reassign",
            entity_id=case.case_id,
            expected_revision=case.revision,
            payload={"assignee_id": "st-10"},
        )
