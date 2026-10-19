"""Bulk verify with undo, through `perform()` (docs/UX.md S3: "if any item
can't be verified, nothing applies and the bad item is named... undo
writes reversing events").
"""

from collections.abc import Iterator

import pytest
from proofline.actions.errors import ActionValidationError
from proofline.actions.service import perform
from proofline.db.models import Base, Event
from proofline.db.repository import get_claim_verification
from proofline.packet import load_packet
from proofline.security.actors import Actor
from proofline.security.permissions import PermissionDenied
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def _event_count(session: Session) -> int:
    return len(list(session.scalars(select(Event))))


PREPARER = Actor(id="st-01", name="Priya", role="preparer", clearance=True)
CLIENT = Actor(id="cu-01", name="Ngozi", role="client", clearance=False)

_REAL_CLAIM_KEYS = [
    "1099b_lot:Northlake Securities:N1",
    "1099b_lot:Northlake Securities:N2",
]


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_bulk_verify_requires_a_detail_review_role(session: Session) -> None:
    packet = load_packet()
    with pytest.raises(PermissionDenied):
        perform(
            session,
            CLIENT,
            "bulk_verify",
            payload={"claim_keys": _REAL_CLAIM_KEYS},
            packet=packet,
        )


def test_bulk_verify_marks_every_claim_verified(session: Session) -> None:
    packet = load_packet()
    result = perform(
        session,
        PREPARER,
        "bulk_verify",
        payload={"claim_keys": _REAL_CLAIM_KEYS},
        packet=packet,
    )
    assert result.current_state["claim_keys"] == _REAL_CLAIM_KEYS
    for claim_key in _REAL_CLAIM_KEYS:
        verification = get_claim_verification(session, claim_key)
        assert verification is not None
        assert verification.verified_by == PREPARER.id
        assert verification.verified_role == "preparer"


def test_bulk_verify_rejects_an_unresolvable_claim_and_writes_nothing(
    session: Session,
) -> None:
    packet = load_packet()
    with pytest.raises(ActionValidationError, match="not-a-real-claim"):
        perform(
            session,
            PREPARER,
            "bulk_verify",
            payload={"claim_keys": [*_REAL_CLAIM_KEYS, "not-a-real-claim"]},
            packet=packet,
        )
    for claim_key in _REAL_CLAIM_KEYS:
        assert get_claim_verification(session, claim_key) is None
    assert _event_count(session) == 0


def test_bulk_verify_requires_a_non_empty_claim_keys_list(session: Session) -> None:
    packet = load_packet()
    with pytest.raises(ActionValidationError):
        perform(
            session, PREPARER, "bulk_verify", payload={"claim_keys": []}, packet=packet
        )


def test_undo_bulk_verify_reverses_a_bulk_verify_event(session: Session) -> None:
    packet = load_packet()
    result = perform(
        session,
        PREPARER,
        "bulk_verify",
        payload={"claim_keys": _REAL_CLAIM_KEYS},
        packet=packet,
    )
    event_id = result.current_state["event_id"]

    undo_result = perform(
        session,
        PREPARER,
        "undo_bulk_verify",
        payload={"event_id": event_id},
        packet=packet,
    )

    assert undo_result.event.event_type == "bulk_claims_verification_undone"
    assert undo_result.event.payload["reverses_event_id"] == event_id
    for claim_key in _REAL_CLAIM_KEYS:
        assert get_claim_verification(session, claim_key) is None


def test_undo_bulk_verify_does_not_clobber_a_later_independent_reverify(
    session: Session,
) -> None:
    """Regression test (reviewer agent): undo used to delete whatever
    `ClaimVerification` row currently existed for each claim key named in
    the event being reversed, regardless of whether that row was actually
    set by *this* event. If claim N1 is verified by event A, then
    independently re-verified by event B, undoing A must leave B's
    verification alone."""
    packet = load_packet()
    claim_key = _REAL_CLAIM_KEYS[0]

    first = perform(
        session,
        PREPARER,
        "bulk_verify",
        payload={"claim_keys": [claim_key]},
        packet=packet,
    )
    second = perform(
        session,
        PREPARER,
        "bulk_verify",
        payload={"claim_keys": [claim_key]},
        packet=packet,
    )
    assert first.current_state["event_id"] != second.current_state["event_id"]

    perform(
        session,
        PREPARER,
        "undo_bulk_verify",
        payload={"event_id": first.current_state["event_id"]},
        packet=packet,
    )

    verification = get_claim_verification(session, claim_key)
    assert verification is not None
    assert verification.verified_by_event_id == second.current_state["event_id"]


def test_undo_bulk_verify_rejects_an_unknown_event_id(session: Session) -> None:
    packet = load_packet()
    with pytest.raises(ActionValidationError):
        perform(
            session,
            PREPARER,
            "undo_bulk_verify",
            payload={"event_id": "00000000-0000-0000-0000-000000000000"},
            packet=packet,
        )


def test_undo_bulk_verify_rejects_a_non_bulk_verify_event(session: Session) -> None:
    packet = load_packet()
    note_result = perform(
        session,
        PREPARER,
        "sync_cases",
        packet=packet,
    )
    with pytest.raises(ActionValidationError):
        perform(
            session,
            PREPARER,
            "undo_bulk_verify",
            payload={"event_id": str(note_result.event.id)},
            packet=packet,
        )
