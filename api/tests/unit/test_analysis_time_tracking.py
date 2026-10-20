"""`time_budget_report`, `hours_logged_by_area` -- reads real `budget_hours`
from the packet, never a hardcoded figure."""

from collections.abc import Iterator
from decimal import Decimal

import pytest
from proofline.analysis.time_tracking import AREA_TO_BUDGET_KEY, time_budget_report
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


def test_every_engine_area_maps_to_a_real_budget_key() -> None:
    packet = load_packet()
    for area, budget_key in AREA_TO_BUDGET_KEY.items():
        assert budget_key in packet.firm.budget_hours, f"{area} -> {budget_key}"


def test_time_budget_report_with_no_entries_logged(session: Session) -> None:
    packet = load_packet()
    report = time_budget_report(session, packet)
    assert len(report) == len(AREA_TO_BUDGET_KEY)
    for row in report:
        assert row.logged_hours == Decimal(0)
        assert row.over_budget is False
        assert row.budget_hours is not None


def test_time_budget_report_flags_over_budget(session: Session) -> None:
    from datetime import UTC, datetime

    from proofline.db.repository import insert_event

    budget = next(
        row.budget_hours
        for row in time_budget_report(session, load_packet())
        if row.area == "identity"
    )
    insert_event(
        session,
        "time_logged",
        {"area": "identity", "hours": str(budget + Decimal(1)), "date": "2026-10-19"},
        actor_id="st-01",
        entity_type="time_entry",
        entity_id="time-1",
        occurred_at=datetime.now(UTC),
    )
    session.commit()

    report = time_budget_report(session, load_packet())
    identity_row = next(row for row in report if row.area == "identity")
    assert identity_row.over_budget is True
