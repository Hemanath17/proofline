"""`outside_filing_items`/`outside_filings_report` -- every item found
generically from the real packet (a diagnostic, the prior preparer's open
items, a related return), never a hardcoded name with no packet reference
behind it."""

from collections.abc import Iterator

import pytest
from proofline.analysis.outside_filings import (
    outside_filing_items,
    outside_filings_report,
)
from proofline.db.models import Base
from proofline.packet import load_packet
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_finds_the_four_known_outside_filings() -> None:
    packet = load_packet()
    items = {found.item for found in outside_filing_items(packet)}
    assert items == {
        "fbar",
        "contractor_1099_nec",
        "form_3520_2023",
        "oregon_composite",
    }


def test_every_item_carries_at_least_one_evidence_ref() -> None:
    packet = load_packet()
    for found in outside_filing_items(packet):
        assert found.evidence_refs, found.item


def test_report_starts_undecided(session: Session) -> None:
    packet = load_packet()
    report = outside_filings_report(session, packet)
    assert all(status.decided is False for status in report)


def test_report_reflects_a_decision(session: Session) -> None:
    from datetime import UTC, datetime

    from proofline.db.repository import insert_event

    insert_event(
        session,
        "outside_filing_decided",
        {"decision": "not_required", "note": "client confirmed filed separately"},
        actor_id="st-01",
        entity_type="outside_filing",
        entity_id="fbar",
        occurred_at=datetime.now(UTC),
    )
    session.commit()

    report = outside_filings_report(session, load_packet())
    fbar = next(status for status in report if status.item == "fbar")
    assert fbar.decided is True
    assert fbar.decision == "not_required"
    assert fbar.decided_by == "st-01"
