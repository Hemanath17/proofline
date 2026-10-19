from collections.abc import Iterator

import pytest
from proofline.actions.errors import ActionConflict, ActionValidationError
from proofline.actions.service import perform
from proofline.db.models import Base, CheckRun, Event, ReviewNote
from proofline.db.repository import EntityNotFound, StaleRevision
from proofline.packet import load_packet
from proofline.security.actors import Actor
from proofline.security.permissions import PermissionDenied
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

REVIEWER = Actor(id="st-02", name="Daniel", role="reviewer", clearance=True)
PREPARER = Actor(id="st-01", name="Priya", role="preparer", clearance=True)
PARTNER = Actor(id="st-03", name="Helen", role="partner", clearance=True)
MARCUS = Actor(id="st-04", name="Marcus", role="preparer", clearance=False)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _event_count(session: Session) -> int:
    return len(session.scalars(select(Event)).all())


def _note_count(session: Session) -> int:
    return len(session.scalars(select(ReviewNote)).all())


# -- I1: a successful action writes the event and the current state
# together; a failed one writes neither. --------------------------------


def test_add_review_note_writes_event_and_current_state_together(
    session: Session,
) -> None:
    result = perform(
        session,
        REVIEWER,
        "add_review_note",
        payload={"about_type": "document", "about_id": "D30", "body": "check this"},
    )
    session.flush()

    assert _event_count(session) == 1
    assert _note_count(session) == 1
    note = result.current_state
    assert note.status == "open"
    assert note.opened_by == "st-02"
    assert note.revision == 1


def test_add_review_note_missing_body_writes_nothing(session: Session) -> None:
    with pytest.raises(ActionValidationError):
        perform(
            session,
            REVIEWER,
            "add_review_note",
            payload={"about_type": "document", "about_id": "D30"},
        )

    assert _event_count(session) == 0
    assert _note_count(session) == 0


def test_permission_denied_action_writes_nothing(session: Session) -> None:
    with pytest.raises(PermissionDenied):
        perform(
            session,
            PREPARER,  # preparer may not raise a review note
            "add_review_note",
            payload={"about_type": "document", "about_id": "D30", "body": "x"},
        )

    assert _event_count(session) == 0
    assert _note_count(session) == 0


# -- I2: a stale revision gets a 409 (here: StaleRevision) with the
# current state, and nothing is written. --------------------------------


def test_respond_with_stale_revision_raises_and_writes_nothing(
    session: Session,
) -> None:
    added = perform(
        session,
        REVIEWER,
        "add_review_note",
        payload={"about_type": "document", "about_id": "D30", "body": "first"},
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
    events_before = _event_count(session)

    with pytest.raises(StaleRevision) as exc_info:
        perform(
            session,
            MARCUS,
            "respond_review_note",
            entity_id=note_id,
            expected_revision=1,  # stale -- it's already 2
            payload={"body": "too late"},
        )

    assert exc_info.value.current["revision"] == 2
    assert _event_count(session) == events_before  # nothing new was written


def test_respond_to_unknown_note_raises_entity_not_found(session: Session) -> None:
    with pytest.raises(EntityNotFound):
        perform(
            session,
            PREPARER,
            "respond_review_note",
            entity_id="note-does-not-exist",
            expected_revision=1,
            payload={"body": "x"},
        )

    assert _event_count(session) == 0


def test_two_racing_responses_exactly_one_succeeds(session: Session) -> None:
    added = perform(
        session,
        REVIEWER,
        "add_review_note",
        payload={"about_type": "document", "about_id": "D30", "body": "first"},
    )
    note_id = added.current_state.id

    first = perform(
        session,
        PREPARER,
        "respond_review_note",
        entity_id=note_id,
        expected_revision=1,
        payload={"body": "a"},
    )
    assert first.current_state.revision == 2

    with pytest.raises(StaleRevision):
        perform(
            session,
            MARCUS,
            "respond_review_note",
            entity_id=note_id,
            expected_revision=1,
            payload={"body": "b"},
        )


# -- resolve_review_note: only the author or the partner. ----------------


def test_resolve_review_note_by_author_succeeds(session: Session) -> None:
    added = perform(
        session,
        REVIEWER,
        "add_review_note",
        payload={"about_type": "document", "about_id": "D30", "body": "x"},
    )
    note_id = added.current_state.id

    result = perform(
        session,
        REVIEWER,
        "resolve_review_note",
        entity_id=note_id,
        expected_revision=1,
        payload={"resolution": "fixed"},
    )

    assert result.current_state.status == "resolved"
    assert result.current_state.resolved_by == "st-02"


def test_resolve_review_note_by_non_author_non_partner_denied_and_writes_nothing(
    session: Session,
) -> None:
    added = perform(
        session,
        REVIEWER,
        "add_review_note",
        payload={"about_type": "document", "about_id": "D30", "body": "x"},
    )
    note_id = added.current_state.id
    events_before = _event_count(session)

    with pytest.raises(PermissionDenied) as exc_info:
        perform(
            session,
            PREPARER,
            "resolve_review_note",
            entity_id=note_id,
            expected_revision=1,
            payload={"resolution": "fixed"},
        )

    assert exc_info.value.rule == (
        "only the reviewer who raised a note, or the partner, may clear it"
    )
    assert _event_count(session) == events_before


def test_resolve_review_note_by_partner_succeeds_even_if_not_author(
    session: Session,
) -> None:
    added = perform(
        session,
        REVIEWER,
        "add_review_note",
        payload={"about_type": "document", "about_id": "D30", "body": "x"},
    )
    note_id = added.current_state.id

    result = perform(
        session,
        PARTNER,
        "resolve_review_note",
        entity_id=note_id,
        expected_revision=1,
        payload={"resolution": "fixed"},
    )

    assert result.current_state.status == "resolved"
    assert result.current_state.resolved_by == "st-03"


def test_respond_to_a_resolved_note_raises_action_conflict_and_writes_nothing(
    session: Session,
) -> None:
    added = perform(
        session,
        REVIEWER,
        "add_review_note",
        payload={"about_type": "document", "about_id": "D30", "body": "x"},
    )
    note_id = added.current_state.id
    perform(
        session,
        PARTNER,
        "resolve_review_note",
        entity_id=note_id,
        expected_revision=1,
        payload={"resolution": "fixed"},
    )
    events_before = _event_count(session)

    with pytest.raises(ActionConflict) as exc_info:
        perform(
            session,
            PREPARER,
            "respond_review_note",
            entity_id=note_id,
            expected_revision=2,
            payload={"body": "too late"},
        )

    assert exc_info.value.detail == "cannot respond to a resolved note"
    assert exc_info.value.current["status"] == "resolved"
    assert exc_info.value.current["id"] == note_id
    assert _event_count(session) == events_before  # nothing new was written


# -- reveal_sensitive_value: clearance required, log-only. ---------------


def test_reveal_sensitive_value_requires_clearance(session: Session) -> None:
    with pytest.raises(PermissionDenied):
        perform(
            session,
            MARCUS,
            "reveal_sensitive_value",
            entity_id="household:theo",
            payload={"field": "ssn"},
        )
    assert _event_count(session) == 0


def test_reveal_sensitive_value_writes_a_log_only_event(session: Session) -> None:
    result = perform(
        session,
        REVIEWER,
        "reveal_sensitive_value",
        entity_id="household:theo",
        payload={"field": "ssn", "reason": "confirming SSN for the client's call"},
    )

    assert result.current_state is None
    assert _event_count(session) == 1
    event = session.scalars(select(Event)).first()
    assert event.event_type == "sensitive_value_revealed"
    assert event.entity_type == "sensitive_value"
    assert event.entity_id == "household:theo"
    assert event.payload["reason"] == "confirming SSN for the client's call"
    assert event.revision is None


def test_reveal_sensitive_value_without_reason_is_rejected(session: Session) -> None:
    with pytest.raises(ActionValidationError, match="reason"):
        perform(
            session,
            REVIEWER,
            "reveal_sensitive_value",
            entity_id="household:theo",
            payload={"field": "ssn"},
        )
    assert _event_count(session) == 0


def test_reveal_sensitive_value_with_blank_reason_is_rejected(session: Session) -> None:
    with pytest.raises(ActionValidationError, match="reason"):
        perform(
            session,
            REVIEWER,
            "reveal_sensitive_value",
            entity_id="household:theo",
            payload={"field": "ssn", "reason": ""},
        )
    assert _event_count(session) == 0


def test_reveal_sensitive_value_with_whitespace_only_reason_is_rejected(
    session: Session,
) -> None:
    """A reason of "   " looks non-blank to a bare `value in (None, "")`
    check but carries nothing a view-log entry should accept."""
    with pytest.raises(ActionValidationError, match="reason"):
        perform(
            session,
            REVIEWER,
            "reveal_sensitive_value",
            entity_id="household:theo",
            payload={"field": "ssn", "reason": "   "},
        )
    assert _event_count(session) == 0


# -- record_check_run ------------------------------------------------------


def test_record_check_run_writes_event_and_check_run(session: Session) -> None:
    packet = load_packet()

    result = perform(session, REVIEWER, "record_check_run", packet=packet)

    assert _event_count(session) == 1
    check_run = session.scalars(select(CheckRun)).first()
    assert check_run is not None
    assert check_run.id == result.current_state.id
    assert isinstance(check_run.findings, list)


def test_record_check_run_denied_for_client(session: Session) -> None:
    from proofline.security.actors import load_actors

    packet = load_packet()
    client_actor = next(
        actor for actor in load_actors(packet).values() if actor.role == "client"
    )

    with pytest.raises(PermissionDenied):
        perform(session, client_actor, "record_check_run", packet=packet)

    assert _event_count(session) == 0


def test_unknown_action_raises_value_error(session: Session) -> None:
    with pytest.raises(ValueError):
        perform(session, REVIEWER, "no_such_action")


# -- Defensive validation for a direct perform() caller that skips the
# fields a real route would always supply. Unreachable through the HTTP
# API (every route always sets entity_id/expected_revision/packet), but
# perform() is a public entry point other code can call directly. --------


def test_respond_review_note_without_entity_id_is_rejected(session: Session) -> None:
    with pytest.raises(ActionValidationError, match="entity_id"):
        perform(session, PREPARER, "respond_review_note", payload={"body": "x"})


def test_respond_review_note_without_expected_revision_is_rejected(
    session: Session,
) -> None:
    with pytest.raises(ActionValidationError, match="expected_revision"):
        perform(
            session,
            PREPARER,
            "respond_review_note",
            entity_id="note-1",
            payload={"body": "x"},
        )


def test_resolve_review_note_without_entity_id_is_rejected(session: Session) -> None:
    with pytest.raises(ActionValidationError, match="entity_id"):
        perform(session, PARTNER, "resolve_review_note", payload={"resolution": "x"})


def test_resolve_review_note_without_expected_revision_is_rejected(
    session: Session,
) -> None:
    with pytest.raises(ActionValidationError, match="expected_revision"):
        perform(
            session,
            PARTNER,
            "resolve_review_note",
            entity_id="note-1",
            payload={"resolution": "x"},
        )


def test_resolve_unknown_note_raises_entity_not_found_before_any_permission_check(
    session: Session,
) -> None:
    """Distinct code path from respond's: resolve_review_note looks the
    note up itself (to check authorship) before apply_revision_cas ever
    runs, so an unknown id is caught there, not inside the CAS helper."""
    with pytest.raises(EntityNotFound):
        perform(
            session,
            PARTNER,
            "resolve_review_note",
            entity_id="note-does-not-exist",
            expected_revision=1,
            payload={"resolution": "x"},
        )


def test_reveal_sensitive_value_without_entity_id_is_rejected(session: Session) -> None:
    with pytest.raises(ActionValidationError, match="entity_id"):
        perform(session, REVIEWER, "reveal_sensitive_value", payload={"field": "ssn"})


def test_record_check_run_without_packet_is_rejected(session: Session) -> None:
    with pytest.raises(ActionValidationError, match="packet"):
        perform(session, REVIEWER, "record_check_run")
