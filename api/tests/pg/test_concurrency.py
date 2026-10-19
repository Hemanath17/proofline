"""The same compare-and-set behavior proven on SQLite in
test_action_service.py, checked here against a real Postgres database with
two genuinely concurrent connections: exactly one of two simultaneous
responses to the same review note succeeds, the other gets a stale-
revision conflict."""

import threading

import pytest
from proofline.actions.service import perform
from proofline.db.repository import StaleRevision
from proofline.security.actors import Actor
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

pytestmark = pytest.mark.pg

REVIEWER = Actor(id="st-02", name="Daniel", role="reviewer", clearance=True)
PREPARER = Actor(id="st-01", name="Priya", role="preparer", clearance=True)
MARCUS = Actor(id="st-04", name="Marcus", role="preparer", clearance=False)


def test_two_concurrent_responses_exactly_one_succeeds(pg_engine: Engine) -> None:
    with Session(pg_engine) as setup_session:
        added = perform(
            setup_session,
            REVIEWER,
            "add_review_note",
            payload={"about_type": "document", "about_id": "D30", "body": "x"},
        )
        setup_session.commit()
        note_id = added.current_state.id

    results: list[str] = []
    barrier = threading.Barrier(2)

    def _respond(actor: Actor, label: str) -> None:
        with Session(pg_engine) as session:
            barrier.wait()
            try:
                perform(
                    session,
                    actor,
                    "respond_review_note",
                    entity_id=note_id,
                    expected_revision=1,
                    payload={"body": f"from {label}"},
                )
                session.commit()
                results.append(f"{label}:ok")
            except StaleRevision:
                session.rollback()
                results.append(f"{label}:conflict")

    threads = [
        threading.Thread(target=_respond, args=(PREPARER, "a")),
        threading.Thread(target=_respond, args=(MARCUS, "b")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    oks = [r for r in results if r.endswith(":ok")]
    conflicts = [r for r in results if r.endswith(":conflict")]
    assert len(oks) == 1
    assert len(conflicts) == 1
