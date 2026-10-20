"""`confirm_outside_filing`, through `perform()`."""

from collections.abc import Iterator

import pytest
from proofline.actions.errors import ActionValidationError
from proofline.actions.service import perform
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


def test_confirm_outside_filing_records_a_decision(session: Session) -> None:
    packet = load_packet()
    result = perform(
        session,
        PREPARER,
        "confirm_outside_filing",
        payload={
            "item": "fbar",
            "decision": "not_required",
            "note": "client confirmed",
        },
        packet=packet,
    )
    assert result.current_state["item"] == "fbar"
    assert result.current_state["decision"] == "not_required"


def test_confirm_outside_filing_rejects_an_unknown_item(session: Session) -> None:
    packet = load_packet()
    with pytest.raises(ActionValidationError, match="item must be one of"):
        perform(
            session,
            PREPARER,
            "confirm_outside_filing",
            payload={"item": "not_a_real_item", "decision": "filed", "note": "x"},
            packet=packet,
        )


def test_confirm_outside_filing_rejects_an_unknown_decision(session: Session) -> None:
    packet = load_packet()
    with pytest.raises(ActionValidationError, match="decision must be one of"):
        perform(
            session,
            PREPARER,
            "confirm_outside_filing",
            payload={"item": "fbar", "decision": "maybe", "note": "x"},
            packet=packet,
        )


def test_confirm_outside_filing_requires_staff(session: Session) -> None:
    packet = load_packet()
    with pytest.raises(PermissionDenied):
        perform(
            session,
            CLIENT,
            "confirm_outside_filing",
            payload={"item": "fbar", "decision": "filed", "note": "x"},
            packet=packet,
        )
