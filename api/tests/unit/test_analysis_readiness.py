"""C5's readiness report, against the real packet."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from proofline.actions.service import perform
from proofline.analysis.readiness import ATTESTATION_ITEMS, readiness_report
from proofline.db.models import Base
from proofline.db.repository import list_cases
from proofline.packet import load_packet
from proofline.security.actors import Actor
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


def _items_by_name(report: dict) -> dict[str, dict]:
    return {item["item"]: item for item in report["items"]}


def test_readiness_is_not_ready_with_nothing_done(session: Session) -> None:
    packet = load_packet()
    report = readiness_report(session, packet)
    assert report["ready_to_file"] is False
    items = _items_by_name(report)
    assert items["engagement_and_consents_signed"]["met"] is True
    assert items["all_documents_accounted_for"]["met"] is False
    assert items["reviewer_sign_off"]["met"] is False
    assert items["partner_sign_off"]["met"] is False
    for item_name in ATTESTATION_ITEMS:
        assert items[item_name]["met"] is False
        assert items[item_name]["reasons"] == ["not yet confirmed"]


def test_estimated_payments_agreed_names_both_mismatches(session: Session) -> None:
    """The packet's own IRS/FTB records don't actually agree with the
    engine's declared estimated payments (a real, un-fixed discrepancy,
    not injected by this test) -- the readiness item must name both."""
    packet = load_packet()
    report = readiness_report(session, packet)
    item = _items_by_name(report)["estimated_payments_agreed"]
    assert item["met"] is False
    assert any("federal" in reason for reason in item["reasons"])
    assert any("California" in reason for reason in item["reasons"])


def test_attestation_item_confirmed_shows_up_in_the_report(session: Session) -> None:
    packet = load_packet()
    when = datetime(2026, 7, 1, tzinfo=UTC)
    perform(
        session,
        PREPARER,
        "confirm_readiness_item",
        payload={"item": "due_diligence_done", "note": "Form 8867 reviewed"},
        occurred_at=when,
        packet=packet,
    )
    report = readiness_report(session, packet)
    item = _items_by_name(report)["due_diligence_done"]
    assert item["met"] is True
    assert item["confirmed_by"] == PREPARER.id
    assert item["note"] == "Form 8867 reviewed"
    assert item["confirmed_at"] == when.isoformat()


def test_sign_off_items_reflect_real_sign_offs(session: Session) -> None:
    packet = load_packet()
    for scope in (
        "identity",
        "wages",
        "investments",
        "business",
        "rentals",
        "pass_throughs",
        "deductions_credits",
        "california",
    ):
        perform(session, REVIEWER, "sign_off", payload={"scope": scope}, packet=packet)
    report = readiness_report(session, packet)
    items = _items_by_name(report)
    assert items["reviewer_sign_off"]["met"] is True
    assert items["partner_sign_off"]["met"] is False

    perform(
        session,
        PARTNER,
        "sign_off",
        payload={"scope": "tax_computation"},
        packet=packet,
    )
    report = readiness_report(session, packet)
    items = _items_by_name(report)
    assert items["reviewer_sign_off"]["met"] is True
    assert items["partner_sign_off"]["met"] is True


def test_no_pending_changes_catches_a_decision_resolved_after_sign_off(
    session: Session,
) -> None:
    """Regression test (reviewer-agent finding): signing off a scope,
    then resolving a case into an adjustment with no engine-side value
    change, must not leave `no_pending_changes` reporting "met" -- a
    resolved decision is its own kind of change (CONTRACTS.md C2: "A
    decision -> Change pending"), not something only a value/scope/
    carry-over change can signal."""
    packet = load_packet()
    perform(session, REVIEWER, "sign_off", payload={"scope": "business"}, packet=packet)
    report = readiness_report(session, packet)
    assert _items_by_name(report)["no_pending_changes"]["met"] is True

    perform(session, REVIEWER, "sync_cases", packet=packet)
    e3_case = next(
        c
        for c in list_cases(session)
        if c.check_id == "THIRD_PARTY_PROCESSOR_INCOME_DOUBLE_COUNTED"
    )
    perform(
        session,
        PREPARER,
        "pick_up",
        entity_id=e3_case.case_id,
        expected_revision=e3_case.revision,
        packet=packet,
    )
    e3_case = next(c for c in list_cases(session) if c.case_id == e3_case.case_id)
    perform(
        session,
        PREPARER,
        "submit_proposal",
        entity_id=e3_case.case_id,
        expected_revision=e3_case.revision,
        payload={
            "resolution_type": "adjust_number",
            "fields": {
                "adjustments": [
                    {"claim": "SchC.1", "old_value": "163700", "new_value": "151300"}
                ]
            },
            "evidence_refs": ["D14", "ev-0103"],
        },
        packet=packet,
    )
    e3_case = next(c for c in list_cases(session) if c.case_id == e3_case.case_id)
    perform(
        session,
        REVIEWER,
        "approve",
        entity_id=e3_case.case_id,
        expected_revision=e3_case.revision,
        payload={},
        packet=packet,
    )  # tax effect ~4,402 federal -> awaiting_partner, not resolved yet
    e3_case = next(c for c in list_cases(session) if c.case_id == e3_case.case_id)
    perform(
        session,
        PARTNER,
        "partner_approve",
        entity_id=e3_case.case_id,
        expected_revision=e3_case.revision,
        payload={},
        packet=packet,
    )

    report = readiness_report(session, packet)
    items = _items_by_name(report)
    assert items["no_pending_changes"]["met"] is False
    assert any(
        "business" in reason for reason in items["no_pending_changes"]["reasons"]
    )


def test_no_open_cases_or_review_notes_names_both_counts(session: Session) -> None:
    packet = load_packet()
    perform(session, REVIEWER, "sync_cases", packet=packet)
    perform(
        session,
        REVIEWER,
        "add_review_note",
        payload={"about_type": "document", "about_id": "D30", "body": "check this"},
    )
    report = readiness_report(session, packet)
    item = _items_by_name(report)["no_open_cases_or_review_notes"]
    assert item["met"] is False
    assert any("open case" in reason for reason in item["reasons"])
    assert any("open review note" in reason for reason in item["reasons"])


def test_carryovers_agreed_is_false_until_the_carryover_is_confirmed(
    session: Session,
) -> None:
    """Same D30/D31 scenario as A2: investments is signed at v1 using D30,
    then D31 arrives -- carryovers_agreed must name investments as
    unconfirmed until `confirm_carryover` runs, exercising the same
    "signed, change pending" detection `no_pending_changes` uses too."""
    packet = load_packet()
    perform(
        session,
        REVIEWER,
        "sign_off",
        payload={"scope": "investments", "version": "v1"},
        packet=packet,
    )
    report = readiness_report(session, packet)
    items = _items_by_name(report)
    assert items["carryovers_agreed"]["met"] is False
    assert "investments" in items["carryovers_agreed"]["reasons"][0]
    assert items["no_pending_changes"]["met"] is False

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
    report = readiness_report(session, packet)
    assert _items_by_name(report)["carryovers_agreed"]["met"] is True


def test_federal_estimated_payments_posted_with_no_transcript_is_zero(
    session: Session,
) -> None:
    packet = load_packet()
    no_transcript_packet = packet.model_copy(
        update={
            "tax_agency_records": packet.tax_agency_records.model_copy(
                update={"irs_account_transcript_2025": []}
            )
        }
    )
    report = readiness_report(session, no_transcript_packet)
    item = _items_by_name(report)["estimated_payments_agreed"]
    assert any(
        "federal estimated payments declared" in reason for reason in item["reasons"]
    )


def test_all_documents_accounted_for_once_every_disposition_is_confirmed(
    session: Session,
) -> None:
    packet = load_packet()
    for document in packet.documents:
        perform(
            session,
            PREPARER,
            "confirm_disposition",
            entity_id=document.id,
            expected_revision=1,
            payload={"disposition": "used"},
            packet=packet,
        )
    report = readiness_report(session, packet)
    item = _items_by_name(report)["all_documents_accounted_for"]
    assert item["met"] is True
    assert item["reasons"] == []
