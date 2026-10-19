"""I5: rebuilding the current state from events gives exactly what's
stored.
"""

from collections.abc import Iterator

import pytest
from proofline.actions.service import perform
from proofline.db.models import Base, CheckRun, Event, ReviewNote
from proofline.db.rebuild import rebuild_current_state
from proofline.packet import load_packet
from proofline.security.actors import Actor
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

REVIEWER = Actor(id="st-02", name="Daniel", role="reviewer", clearance=True)
PREPARER = Actor(id="st-01", name="Priya", role="preparer", clearance=True)
PARTNER = Actor(id="st-03", name="Helen", role="partner", clearance=True)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _review_note_snapshot(session: Session) -> dict[str, dict]:
    notes = session.scalars(select(ReviewNote)).all()
    return {note.id: note.to_dict() for note in notes}


def _check_run_snapshot(session: Session) -> dict[str, dict]:
    runs = session.scalars(select(CheckRun)).all()
    return {run.id: run.to_dict() for run in runs}


def test_rebuild_matches_the_live_current_state(session: Session) -> None:
    packet = load_packet()

    added = perform(
        session,
        REVIEWER,
        "add_review_note",
        payload={"about_type": "document", "about_id": "D30", "body": "check this"},
    )
    note_id = added.current_state.id
    perform(
        session,
        PREPARER,
        "respond_review_note",
        entity_id=note_id,
        expected_revision=1,
        payload={"body": "responding"},
    )
    perform(
        session,
        PARTNER,
        "resolve_review_note",
        entity_id=note_id,
        expected_revision=2,
        payload={"resolution": "fixed"},
    )
    perform(session, REVIEWER, "record_check_run", packet=packet)
    perform(
        session,
        REVIEWER,
        "reveal_sensitive_value",
        entity_id="household:theo",
        payload={"field": "ssn", "reason": "confirming for the client's call"},
    )
    session.flush()

    live_notes = _review_note_snapshot(session)
    live_check_runs = _check_run_snapshot(session)
    events_before = len(session.scalars(select(Event)).all())

    rebuild_current_state(session)
    session.flush()

    assert _review_note_snapshot(session) == live_notes
    assert _check_run_snapshot(session) == live_check_runs
    # Rebuilding never touches events themselves.
    assert len(session.scalars(select(Event)).all()) == events_before


def test_rebuild_is_idempotent(session: Session) -> None:
    perform(
        session,
        REVIEWER,
        "add_review_note",
        payload={"about_type": "document", "about_id": "D30", "body": "x"},
    )
    session.flush()

    rebuild_current_state(session)
    session.flush()
    first = _review_note_snapshot(session)

    rebuild_current_state(session)
    session.flush()
    second = _review_note_snapshot(session)

    assert first == second


def test_rebuild_skips_events_with_no_registered_handler(session: Session) -> None:
    """An old Step 1 "test_event" row (or any event type rebuild doesn't
    know how to replay) is read and skipped, not an error."""
    from proofline.db.repository import insert_event

    insert_event(session, "test_event", {"foo": "bar"})
    session.flush()

    rebuild_current_state(session)  # must not raise
