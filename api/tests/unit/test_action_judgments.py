"""`record_judgment_election`, through `perform()`."""

from collections.abc import Iterator

import pytest
from proofline.actions.errors import ActionValidationError
from proofline.actions.service import perform
from proofline.analysis.judgments import list_judgments
from proofline.db.models import Base
from proofline.packet import load_packet
from proofline.security.actors import Actor
from proofline.security.permissions import PermissionDenied
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

REVIEWER = Actor(id="st-02", name="Daniel", role="reviewer", clearance=True)
CLIENT = Actor(id="cu-01", name="Ngozi", role="client", clearance=False)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_record_a_plain_judgment(session: Session) -> None:
    packet = load_packet()
    result = perform(
        session,
        REVIEWER,
        "record_judgment_election",
        payload={
            "authority": "IRC 1014",
            "approved_by": "st-02",
            "reasoning": "basis step-up confirmed against the estate records",
            "claim_key": "household:ngozi:basis",
        },
        packet=packet,
    )
    assert result.current_state["is_election"] is False
    judgments = list_judgments(session)
    assert len(judgments) == 1
    assert judgments[0].authority == "IRC 1014"


def test_record_an_election_needs_a_real_what_if_id(session: Session) -> None:
    packet = load_packet()
    with pytest.raises(ActionValidationError, match="no what-if alternative"):
        perform(
            session,
            REVIEWER,
            "record_judgment_election",
            payload={
                "authority": "IRC 179",
                "approved_by": "st-02",
                "reasoning": "elected section 179",
                "is_election": True,
                "what_if_id": "not_a_real_alternative",
            },
            packet=packet,
        )


def test_record_an_election_tied_to_a_real_what_if(session: Session) -> None:
    packet = load_packet()
    result = perform(
        session,
        REVIEWER,
        "record_judgment_election",
        payload={
            "authority": "IRC 179",
            "approved_by": "st-02",
            "reasoning": "elected section 179 for studio equipment",
            "is_election": True,
            "what_if_id": "equipment_section179",
        },
        packet=packet,
    )
    assert result.current_state["what_if_id"] == "equipment_section179"


def test_an_election_without_a_what_if_id_is_rejected(session: Session) -> None:
    packet = load_packet()
    with pytest.raises(ActionValidationError, match="an election needs what_if_id"):
        perform(
            session,
            REVIEWER,
            "record_judgment_election",
            payload={
                "authority": "IRC 179",
                "approved_by": "st-02",
                "reasoning": "elected section 179",
                "is_election": True,
            },
            packet=packet,
        )


def test_record_judgment_requires_staff(session: Session) -> None:
    packet = load_packet()
    with pytest.raises(PermissionDenied):
        perform(
            session,
            CLIENT,
            "record_judgment_election",
            payload={"authority": "x", "approved_by": "x", "reasoning": "x"},
            packet=packet,
        )
