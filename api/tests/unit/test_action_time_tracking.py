"""`log_time`, through `perform()`."""

from collections.abc import Iterator
from decimal import Decimal

import pytest
from proofline.actions.errors import ActionValidationError
from proofline.actions.service import perform
from proofline.analysis.time_tracking import list_time_entries
from proofline.db.models import Base
from proofline.packet import load_packet
from proofline.security.actors import Actor
from proofline.security.permissions import PermissionDenied
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

PREPARER = Actor(id="st-01", name="Priya", role="preparer", clearance=True)
CLIENT = Actor(id="cu-01", name="Ngozi", role="client", clearance=False)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_log_time_records_an_event(session: Session) -> None:
    packet = load_packet()
    result = perform(
        session,
        PREPARER,
        "log_time",
        payload={"area": "investments", "hours": "2.5", "date": "2026-10-19"},
        packet=packet,
    )
    assert result.current_state["area"] == "investments"
    assert result.current_state["hours"] == "2.5"

    entries = list_time_entries(session)
    assert len(entries) == 1
    assert entries[0].area == "investments"
    assert entries[0].hours == Decimal("2.5")
    assert entries[0].actor_id == PREPARER.id


def test_log_time_rejects_an_unknown_area(session: Session) -> None:
    packet = load_packet()
    with pytest.raises(ActionValidationError, match="area must be one of"):
        perform(
            session,
            PREPARER,
            "log_time",
            payload={"area": "not_a_real_area", "hours": "1", "date": "2026-10-19"},
            packet=packet,
        )


def test_log_time_rejects_non_positive_hours(session: Session) -> None:
    packet = load_packet()
    with pytest.raises(ActionValidationError, match="hours must be"):
        perform(
            session,
            PREPARER,
            "log_time",
            payload={"area": "investments", "hours": "0", "date": "2026-10-19"},
            packet=packet,
        )


def test_log_time_requires_staff(session: Session) -> None:
    packet = load_packet()
    with pytest.raises(PermissionDenied):
        perform(
            session,
            CLIENT,
            "log_time",
            payload={"area": "investments", "hours": "1", "date": "2026-10-19"},
            packet=packet,
        )
