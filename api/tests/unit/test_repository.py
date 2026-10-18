from collections.abc import Iterator

import pytest
from proofline.db.models import Base, Event
from proofline.db.repository import (
    _needs_sqlite_seq_placeholder,
    get_event,
    insert_event,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_insert_and_get_event(session: Session) -> None:
    written = insert_event(session, "test_event", {"foo": "bar"})

    read_back = get_event(session, written.id)

    assert read_back is not None
    assert read_back.id == written.id
    assert read_back.event_type == "test_event"
    assert read_back.payload == {"foo": "bar"}
    assert read_back.schema_version == 1


def test_get_event_missing_returns_none(session: Session) -> None:
    import uuid

    assert get_event(session, uuid.uuid4()) is None


def test_sqlite_seq_placeholder_applies_only_to_sqlite() -> None:
    """The one gate standing between "SQLite needs a placeholder" and
    "every other dialect relies on the database's own identity sequence"
    must actually be dialect-specific, not just true by coincidence in the
    test fixtures. Both engines here are only ever constructed, never
    connected to -- this doesn't touch a network, including for postgresql."""
    sqlite_session = Session(create_engine("sqlite:///:memory:"))
    postgres_session = Session(
        create_engine("postgresql+psycopg://user:pass@localhost/db")
    )
    try:
        assert _needs_sqlite_seq_placeholder(sqlite_session) is True
        assert _needs_sqlite_seq_placeholder(postgres_session) is False
    finally:
        sqlite_session.close()
        postgres_session.close()


def test_event_seq_has_no_python_side_default() -> None:
    """If Event.seq ever grew a Python-side default, SQLAlchemy would send
    it explicitly on every insert -- including to Postgres, silently
    overriding its identity sequence instead of letting the database
    assign it. A transient Event's `seq` must start out unset."""
    event = Event(event_type="x", payload={})

    assert event.seq is None


def test_insert_event_on_sqlite_sets_the_placeholder_before_insert(
    session: Session,
) -> None:
    """insert_event's sqlite branch must actually run for a sqlite session
    (the fixture here is sqlite), confirming the placeholder is what let
    the NOT NULL column accept the row -- not a coincidental default."""
    written = insert_event(session, "test_event", {"foo": "bar"})

    assert written.seq == 0
