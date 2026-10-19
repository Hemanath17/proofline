"""C4 document disposition confirmation, through `perform()`
(docs/CONTRACTS.md C4).
"""

from collections.abc import Iterator

import pytest
from proofline.actions.errors import ActionValidationError
from proofline.actions.service import perform
from proofline.db.models import Base
from proofline.db.repository import StaleRevision, get_or_create_document_disposition
from proofline.packet import load_packet
from proofline.security.actors import Actor
from proofline.security.permissions import PermissionDenied
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

PREPARER = Actor(id="st-01", name="Priya", role="preparer", clearance=True)
REVIEWER = Actor(id="st-02", name="Daniel", role="reviewer", clearance=True)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_confirm_disposition_requires_the_preparer(session: Session) -> None:
    packet = load_packet()
    with pytest.raises(PermissionDenied):
        perform(
            session,
            REVIEWER,
            "confirm_disposition",
            entity_id="D10",
            expected_revision=1,
            payload={"disposition": "duplicate_of", "reason": "same as D09"},
            packet=packet,
        )


def test_confirm_disposition_creates_the_row_lazily_then_confirms_it(
    session: Session,
) -> None:
    packet = load_packet()
    result = perform(
        session,
        PREPARER,
        "confirm_disposition",
        entity_id="D10",
        expected_revision=1,
        payload={"disposition": "duplicate_of", "reason": "same as D09"},
        packet=packet,
    )
    row = result.current_state
    assert row.document_id == "D10"
    assert row.disposition == "duplicate_of"
    assert row.reason == "same as D09"
    assert row.confirmed_by == PREPARER.id
    assert row.revision == 2


def test_confirm_disposition_rejects_an_unknown_disposition(session: Session) -> None:
    packet = load_packet()
    with pytest.raises(ActionValidationError):
        perform(
            session,
            PREPARER,
            "confirm_disposition",
            entity_id="D10",
            expected_revision=1,
            payload={"disposition": "not_a_real_disposition"},
            packet=packet,
        )


@pytest.mark.parametrize("disposition", ["excluded", "superseded_by", "duplicate_of"])
def test_confirm_disposition_requires_a_reason_for_some_dispositions(
    session: Session, disposition: str
) -> None:
    packet = load_packet()
    with pytest.raises(ActionValidationError, match="reason"):
        perform(
            session,
            PREPARER,
            "confirm_disposition",
            entity_id="D10",
            expected_revision=1,
            payload={"disposition": disposition},
            packet=packet,
        )


def test_confirm_disposition_does_not_require_a_reason_for_used(
    session: Session,
) -> None:
    packet = load_packet()
    result = perform(
        session,
        PREPARER,
        "confirm_disposition",
        entity_id="D09",
        expected_revision=1,
        payload={"disposition": "used"},
        packet=packet,
    )
    assert result.current_state.disposition == "used"


def test_confirm_disposition_stale_revision_returns_current_state(
    session: Session,
) -> None:
    packet = load_packet()
    get_or_create_document_disposition(session, "D10")
    with pytest.raises(StaleRevision) as exc_info:
        perform(
            session,
            PREPARER,
            "confirm_disposition",
            entity_id="D10",
            expected_revision=99,
            payload={"disposition": "used"},
            packet=packet,
        )
    assert exc_info.value.current["document_id"] == "D10"


def test_confirm_disposition_requires_expected_revision(session: Session) -> None:
    packet = load_packet()
    with pytest.raises(ActionValidationError):
        perform(
            session,
            PREPARER,
            "confirm_disposition",
            entity_id="D10",
            expected_revision=None,
            payload={"disposition": "used"},
            packet=packet,
        )
