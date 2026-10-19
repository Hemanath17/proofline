"""`confirm_readiness_item`, through `perform()`."""

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


def test_confirm_readiness_item_records_an_event(session: Session) -> None:
    packet = load_packet()
    result = perform(
        session,
        PREPARER,
        "confirm_readiness_item",
        payload={"item": "identity_verified", "note": "checked against D71"},
        packet=packet,
    )
    assert result.current_state["item"] == "identity_verified"
    assert result.current_state["confirmed_by"] == PREPARER.id
    assert result.current_state["note"] == "checked against D71"


def test_confirm_readiness_item_rejects_an_unknown_item(session: Session) -> None:
    packet = load_packet()
    with pytest.raises(ActionValidationError, match="item must be one of"):
        perform(
            session,
            PREPARER,
            "confirm_readiness_item",
            payload={"item": "not_a_real_item", "note": "x"},
            packet=packet,
        )


def test_confirm_readiness_item_requires_a_note(session: Session) -> None:
    packet = load_packet()
    with pytest.raises(ActionValidationError, match="note is required"):
        perform(
            session,
            PREPARER,
            "confirm_readiness_item",
            payload={"item": "identity_verified"},
            packet=packet,
        )


def test_confirm_readiness_item_requires_staff(session: Session) -> None:
    packet = load_packet()
    with pytest.raises(PermissionDenied):
        perform(
            session,
            CLIENT,
            "confirm_readiness_item",
            payload={"item": "identity_verified", "note": "x"},
            packet=packet,
        )
