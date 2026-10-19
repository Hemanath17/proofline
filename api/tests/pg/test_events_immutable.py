"""I6: the database refuses to update or delete any event (and refuses a
TRUNCATE too)."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DatabaseError

pytestmark = pytest.mark.pg


def _insert_one_event(engine: Engine) -> None:
    with engine.connect() as connection:
        connection.execute(
            text(
                "INSERT INTO events (id, event_type, payload, schema_version) "
                "VALUES (:id, :event_type, CAST(:payload AS jsonb), 1)"
            ),
            {"id": str(uuid.uuid4()), "event_type": "test_event", "payload": "{}"},
        )
        connection.commit()


def test_update_is_refused(pg_engine: Engine) -> None:
    _insert_one_event(pg_engine)
    with pg_engine.connect() as connection, pytest.raises(DatabaseError):
        connection.execute(text("UPDATE events SET event_type = 'changed'"))
        connection.commit()


def test_delete_is_refused(pg_engine: Engine) -> None:
    _insert_one_event(pg_engine)
    with pg_engine.connect() as connection, pytest.raises(DatabaseError):
        connection.execute(text("DELETE FROM events"))
        connection.commit()


def test_truncate_is_refused(pg_engine: Engine) -> None:
    _insert_one_event(pg_engine)
    with pg_engine.connect() as connection, pytest.raises(DatabaseError):
        connection.execute(text("TRUNCATE events"))
        connection.commit()
