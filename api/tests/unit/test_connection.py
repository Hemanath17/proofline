import pytest
from proofline.db.connection import (
    DatabaseUnavailable,
    check_connection,
    get_database_url,
    get_session,
)
from proofline.db.models import Base, Event
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def test_check_connection_succeeds_against_a_reachable_database() -> None:
    engine = create_engine("sqlite:///:memory:")

    check_connection(engine)  # must not raise


def test_check_connection_raises_against_an_unreachable_database() -> None:
    engine = create_engine("sqlite:////nonexistent/path/does-not-exist.db")

    with pytest.raises(Exception):  # noqa: B017 -- any driver error counts
        check_connection(engine)


def test_get_database_url_raises_a_clear_error_when_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(DatabaseUnavailable):
        get_database_url()


def test_get_database_url_defaults_to_sslmode_require(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@host/db")

    url = get_database_url()

    assert url.query["sslmode"] == "require"
    assert url.drivername == "postgresql+psycopg"


def test_get_session_commits_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """`get_session`'s real implementation -- every route test overrides
    this dependency with its own fixture, so without this test the actual
    commit-on-success / rollback-on-exception wiring (the thing I1 relies
    on at the request level) would never run in the test suite at all."""
    from proofline.db.repository import insert_event

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    monkeypatch.setattr("proofline.db.connection.get_engine", lambda: engine)

    generator = get_session()
    session = next(generator)
    insert_event(session, "test_event", {"foo": "bar"})
    with pytest.raises(StopIteration):
        next(generator)  # resumes past `yield`, runs session.commit()

    with Session(engine) as check_session:
        assert len(check_session.scalars(select(Event)).all()) == 1


def test_get_session_rolls_back_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    from proofline.db.repository import insert_event

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    monkeypatch.setattr("proofline.db.connection.get_engine", lambda: engine)

    generator = get_session()
    session = next(generator)
    insert_event(session, "test_event", {"foo": "bar"})
    with pytest.raises(ValueError):
        generator.throw(ValueError("boom"))  # as Starlette does when a route raises

    with Session(engine) as check_session:
        assert len(check_session.scalars(select(Event)).all()) == 0
