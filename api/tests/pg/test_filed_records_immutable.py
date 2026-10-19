"""I6: the database refuses to update or delete the filed record (and
refuses a TRUNCATE too) -- same pattern as `test_events_immutable.py`,
proven against a real Postgres database since SQLite can't express the
same trigger (see the migration's own comment)."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DatabaseError

pytestmark = pytest.mark.pg


def _insert_one_event(engine: Engine) -> str:
    event_id = str(uuid.uuid4())
    with engine.connect() as connection:
        connection.execute(
            text(
                "INSERT INTO events (id, event_type, payload, schema_version) "
                "VALUES (:id, :event_type, CAST(:payload AS jsonb), 1)"
            ),
            {"id": event_id, "event_type": "test_event", "payload": "{}"},
        )
        connection.commit()
    return event_id


def _insert_one_filed_record(engine: Engine) -> str:
    event_id = _insert_one_event(engine)
    record_id = f"filed-{uuid.uuid4()}"
    with engine.connect() as connection:
        connection.execute(
            text(
                "INSERT INTO filed_records "
                "(id, jurisdiction, package_reference, amounts_fingerprint, "
                "identity_fingerprint, accepted_at, submission_event_id) "
                "VALUES (:id, 'federal', 'ref', 'amt', 'ident', now(), "
                ":submission_event_id)"
            ),
            {"id": record_id, "submission_event_id": event_id},
        )
        connection.commit()
    return record_id


def test_update_is_refused(pg_engine: Engine) -> None:
    _insert_one_filed_record(pg_engine)
    with pg_engine.connect() as connection, pytest.raises(DatabaseError):
        connection.execute(text("UPDATE filed_records SET jurisdiction = 'california'"))
        connection.commit()


def test_delete_is_refused(pg_engine: Engine) -> None:
    _insert_one_filed_record(pg_engine)
    with pg_engine.connect() as connection, pytest.raises(DatabaseError):
        connection.execute(text("DELETE FROM filed_records"))
        connection.commit()


def test_truncate_is_refused(pg_engine: Engine) -> None:
    _insert_one_filed_record(pg_engine)
    with pg_engine.connect() as connection, pytest.raises(DatabaseError):
        connection.execute(text("TRUNCATE filed_records"))
        connection.commit()


def test_update_is_still_refused_after_a_normal_commit(pg_engine: Engine) -> None:
    """The guard survives a normal, successful transaction -- not just an
    update attempted in the same transaction as the insert."""
    record_id = _insert_one_filed_record(pg_engine)
    with pg_engine.connect() as connection:
        found = connection.execute(
            text("SELECT id FROM filed_records WHERE id = :id"), {"id": record_id}
        ).scalar_one()
    assert found == record_id

    with pg_engine.connect() as connection, pytest.raises(DatabaseError):
        connection.execute(
            text("UPDATE filed_records SET jurisdiction = 'california' WHERE id = :id"),
            {"id": record_id},
        )
        connection.commit()
