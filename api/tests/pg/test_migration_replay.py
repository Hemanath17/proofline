"""I7: applying a new migration to a database full of past events leaves
every event readable, and rebuilding gives the same state as before.

`pg_engine` already resets the schema and migrates to head; this test
steps back down to the schema Step 1-3 actually shipped, inserts an event
shaped the way that code wrote it (no actor_id/entity_type/entity_id/
revision/occurred_at at all), then migrates forward again the way a real
deploy would -- and checks the old row is still there, with the new
columns NULL, and that `rebuild_current_state` gives the same (empty, for
this event type) current state before and after.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid

import pytest
from proofline.db.models import CheckRun, ReviewNote
from proofline.db.rebuild import rebuild_current_state
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from tests.pg.conftest import (
    _API_DIR,
    _normalized_url,
    _test_database_url,
    _upgrade_head,
)

pytestmark = pytest.mark.pg


def _downgrade_to(raw_test_url: str, revision: str) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(_API_DIR / "alembic.ini"),
            "downgrade",
            revision,
        ],
        cwd=_API_DIR,
        env={**os.environ, "DATABASE_URL": raw_test_url},
        check=True,
    )


def _current_state_snapshot(session: Session) -> dict:
    notes = {note.id: note.to_dict() for note in session.scalars(select(ReviewNote))}
    runs = {run.id: run.to_dict() for run in session.scalars(select(CheckRun))}
    return {"review_notes": notes, "check_runs": runs}


def test_old_shaped_events_survive_the_new_migrations_and_rebuild_matches(
    pg_engine: Engine,
) -> None:
    raw_test_url = _test_database_url()
    _downgrade_to(raw_test_url, "41f2af2e559e")  # the pre-Step-4 schema

    old_event_id = uuid.uuid4()
    engine = create_engine(_normalized_url(raw_test_url))
    try:
        with engine.connect() as connection:
            connection.execute(
                text(
                    "INSERT INTO events (id, event_type, payload, schema_version) "
                    "VALUES (:id, 'test_event', CAST(:payload AS jsonb), 1)"
                ),
                {"id": str(old_event_id), "payload": '{"foo": "bar"}'},
            )
            connection.commit()

        _upgrade_head(raw_test_url)

        with Session(engine) as session:
            row = session.execute(
                text(
                    "SELECT actor_id, entity_type, entity_id, revision, occurred_at "
                    "FROM events WHERE id = :id"
                ),
                {"id": str(old_event_id)},
            ).one()
            assert row.actor_id is None
            assert row.entity_type is None
            assert row.entity_id is None
            assert row.revision is None
            assert row.occurred_at is None

            before = _current_state_snapshot(session)
            rebuild_current_state(session)
            session.commit()
            after = _current_state_snapshot(session)

        assert before == after == {"review_notes": {}, "check_runs": {}}
    finally:
        engine.dispose()
