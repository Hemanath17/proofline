from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, TypeVar

from sqlalchemy import inspect, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from proofline.db.canonical import prepare_payload_for_storage
from proofline.db.models import (
    Adjustment,
    Case,
    CaseDecision,
    CaseProposal,
    CheckRun,
    ClaimVerification,
    DocumentDisposition,
    Event,
    LastSeen,
    ReviewNote,
    SignOff,
)

_Model = TypeVar("_Model", ReviewNote, CheckRun, Case, DocumentDisposition)


class StaleRevision(Exception):
    """Raised when a compare-and-set update's WHERE clause matched no row
    because the caller's `expected_revision` is no longer current. Carries
    the row as it actually stands now, as a plain dict (`current.to_dict()`,
    captured by the raise site while the session is still open) so the
    caller can return it in a 409 (redacted for whoever's asking) per
    CONTRACTS.md and acceptance test I2 -- never the ORM row itself, which
    would raise `DetachedInstanceError` the moment anything touches it
    after the request's session closes (confirmed over HTTP against real
    Postgres: a racing stale revision came back 500, not 409)."""

    def __init__(self, current: dict[str, Any]):
        self.current = current


class EntityNotFound(Exception):
    """Raised when a compare-and-set update's WHERE clause matched no row
    because no row with that id exists at all -- distinct from a stale
    revision, which means the row exists but has moved on."""


def _needs_sqlite_seq_placeholder(session: Session) -> bool:
    """True only for the SQLite test fixtures. SQLite has no equivalent to
    Postgres's identity column, so it can't generate `seq` itself -- every
    other dialect (postgresql in production) must rely on the database's
    own identity sequence, never on application code, to assign `seq`. This
    is the one place that decides which case applies, kept as its own
    function so that decision is tested directly rather than trusted by
    inspection."""
    return session.get_bind().dialect.name == "sqlite"


def insert_event(
    session: Session,
    event_type: str,
    payload: dict,
    *,
    actor_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    revision: int | None = None,
    occurred_at: datetime | None = None,
    schema_version: int = 1,
) -> Event:
    """Writes one event. `payload` is run through
    `prepare_payload_for_storage` first, so a caller building a payload out
    of domain objects (which naturally carry `Decimal`) never has to
    remember to convert it -- every event gets this for free.

    Does not commit: callers inside the action service share one
    transaction with their current-state write and must commit or roll
    back together (I1). A bare call from a test is responsible for its own
    commit, same as before.
    """
    event = Event(
        event_type=event_type,
        payload=prepare_payload_for_storage(payload),
        actor_id=actor_id,
        entity_type=entity_type,
        entity_id=entity_id,
        revision=revision,
        occurred_at=occurred_at,
        schema_version=schema_version,
    )
    if _needs_sqlite_seq_placeholder(session):
        # A fixed placeholder satisfies the NOT NULL constraint; nothing
        # reads this column's value yet.
        event.seq = 0
    session.add(event)
    session.flush()
    return event


def get_event(session: Session, event_id: uuid.UUID) -> Event | None:
    return session.get(Event, event_id)


def list_events_for_entity(
    session: Session, entity_type: str, entity_id: str
) -> list[Event]:
    """The activity timeline for one entity (docs/UX.md S2 "Activity"),
    oldest first -- callers that want newest-first (the UX spec's order)
    reverse this themselves, since "oldest first" is also what a
    chronological replay/debugging read wants."""
    statement = (
        select(Event)
        .where(Event.entity_type == entity_type, Event.entity_id == entity_id)
        .order_by(Event.seq, Event.created_at)
    )
    return list(session.scalars(statement))


def apply_revision_cas(
    session: Session,
    model: type[_Model],
    pk_value: str,
    expected_revision: int,
    values: dict[str, Any],
) -> _Model:
    """UPDATE ... WHERE id = :pk_value AND revision = :expected_revision,
    bumping `revision` by one and setting `values` in the same statement.
    This is the single SQL statement that makes the compare-and-set
    atomic: two callers racing on the same row can each only ever match it
    while its revision is still `expected_revision`, so at most one UPDATE
    can succeed (`rowcount == 1`); the other's `rowcount` comes back 0,
    with no error and no partial write (acceptance test I2).

    Raises `EntityNotFound` if no row with that id exists at all, or
    `StaleRevision(current)` if the row exists but had already moved past
    `expected_revision`.

    Reads the model's primary-key column via `inspect()` rather than
    assuming it's named `id` -- `Case`'s primary key is `case_id`, unlike
    `ReviewNote`/`CheckRun`.
    """
    (pk_column,) = inspect(model).primary_key
    result = session.execute(
        update(model)
        .where(pk_column == pk_value, model.revision == expected_revision)
        .values(revision=expected_revision + 1, **values)
        # Explicit, rather than relying on "auto"/"evaluate" to update any
        # already-loaded copy of this row in the session's identity map --
        # confirmed by hand that "evaluate" can silently sync some of a
        # multi-column SET onto a cached object but not others. Refreshing
        # from the database below is the one way that's actually reliable.
        .execution_options(synchronize_session=False)
    )
    if result.rowcount == 1:
        session.flush()
        row = session.get(model, pk_value)
        session.refresh(row)
        return row  # type: ignore[return-value]
    current = session.get(model, pk_value)
    if current is None:
        raise EntityNotFound(pk_value)
    session.refresh(current)
    raise StaleRevision(current.to_dict())


def insert_review_note(session: Session, note: ReviewNote) -> ReviewNote:
    session.add(note)
    session.flush()
    return note


def get_review_note(session: Session, note_id: str) -> ReviewNote | None:
    return session.get(ReviewNote, note_id)


def list_review_notes(
    session: Session, *, about_type: str | None = None, about_id: str | None = None
) -> list[ReviewNote]:
    statement = select(ReviewNote).order_by(ReviewNote.opened_at)
    if about_type is not None:
        statement = statement.where(ReviewNote.about_type == about_type)
    if about_id is not None:
        statement = statement.where(ReviewNote.about_id == about_id)
    return list(session.scalars(statement))


def insert_check_run(session: Session, check_run: CheckRun) -> CheckRun:
    session.add(check_run)
    session.flush()
    return check_run


def record_last_seen(
    session: Session, actor_id: str, entity_type: str, entity_id: str, seen_at: datetime
) -> None:
    """Plain upsert -- UI state (docs/UX.md "Since you last looked"), not a
    workpaper event, so there's no revision check and no event write.
    Dialect-specific upsert because SQLite (unit tests) and Postgres
    (production) use different `ON CONFLICT` builders."""
    insert_fn = (
        sqlite_insert if session.get_bind().dialect.name == "sqlite" else pg_insert
    )
    statement = insert_fn(LastSeen).values(
        actor_id=actor_id, entity_type=entity_type, entity_id=entity_id, seen_at=seen_at
    )
    statement = statement.on_conflict_do_update(
        index_elements=["actor_id", "entity_type", "entity_id"],
        set_={"seen_at": seen_at},
    )
    session.execute(statement)
    session.flush()


def get_last_seen(
    session: Session, actor_id: str, entity_type: str, entity_id: str
) -> datetime | None:
    row = session.get(LastSeen, (actor_id, entity_type, entity_id))
    return None if row is None else row.seen_at


def insert_case(session: Session, case: Case) -> Case:
    session.add(case)
    session.flush()
    return case


def get_case(session: Session, case_id: str) -> Case | None:
    return session.get(Case, case_id)


def get_case_by_root_cause_key(session: Session, root_cause_key: str) -> Case | None:
    statement = select(Case).where(Case.root_cause_key == root_cause_key)
    return session.scalars(statement).one_or_none()


def list_cases(session: Session) -> list[Case]:
    return list(session.scalars(select(Case).order_by(Case.created_at)))


def insert_case_proposal(session: Session, proposal: CaseProposal) -> CaseProposal:
    session.add(proposal)
    session.flush()
    return proposal


def list_case_proposals(session: Session, case_id: str) -> list[CaseProposal]:
    statement = (
        select(CaseProposal)
        .where(CaseProposal.case_id == case_id)
        .order_by(CaseProposal.revision_number)
    )
    return list(session.scalars(statement))


def get_case_proposal(
    session: Session, case_id: str, revision_number: int
) -> CaseProposal | None:
    statement = select(CaseProposal).where(
        CaseProposal.case_id == case_id,
        CaseProposal.revision_number == revision_number,
    )
    return session.scalars(statement).one_or_none()


def insert_case_decision(session: Session, decision: CaseDecision) -> CaseDecision:
    session.add(decision)
    session.flush()
    return decision


def list_case_decisions(session: Session, case_id: str) -> list[CaseDecision]:
    statement = (
        select(CaseDecision)
        .where(CaseDecision.case_id == case_id)
        .order_by(CaseDecision.decided_at)
    )
    return list(session.scalars(statement))


def insert_adjustment(session: Session, adjustment: Adjustment) -> Adjustment:
    session.add(adjustment)
    session.flush()
    return adjustment


def list_adjustments(session: Session) -> list[Adjustment]:
    return list(session.scalars(select(Adjustment).order_by(Adjustment.created_at)))


def insert_sign_off(session: Session, sign_off: SignOff) -> SignOff:
    session.add(sign_off)
    session.flush()
    return sign_off


def list_sign_offs(session: Session, scope: str) -> list[SignOff]:
    statement = select(SignOff).where(SignOff.scope == scope).order_by(SignOff.version)
    return list(session.scalars(statement))


def get_latest_sign_off(session: Session, scope: str) -> SignOff | None:
    sign_offs = list_sign_offs(session, scope)
    return sign_offs[-1] if sign_offs else None


def get_document_disposition(
    session: Session, document_id: str
) -> DocumentDisposition | None:
    return session.get(DocumentDisposition, document_id)


def get_or_create_document_disposition(
    session: Session, document_id: str
) -> DocumentDisposition:
    """Every document has a disposition row, defaulting to `pending`
    (CONTRACTS.md C4) -- created lazily on first read/write rather than
    backfilled for all 74+ packet documents up front.

    Two concurrent first-time `confirm_disposition` calls on the same
    never-before-disposed document could otherwise both see `existing is
    None` and both try to insert the same primary key -- caught by
    `document_dispositions`'s own primary-key constraint at the database
    level, which would otherwise surface as an uncaught
    `sqlalchemy.exc.IntegrityError` (a bare 500) instead of just handing
    back whoever actually won, the same race class fixed in
    `actions.sign_offs.sign_off` (see docs/DECISIONS.md)."""
    existing = get_document_disposition(session, document_id)
    if existing is not None:
        return existing
    created = DocumentDisposition(
        document_id=document_id, disposition="pending", revision=1
    )
    session.add(created)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        existing = get_document_disposition(session, document_id)
        if existing is not None:
            return existing
        raise
    return created


def get_claim_verification(
    session: Session, claim_key: str
) -> ClaimVerification | None:
    return session.get(ClaimVerification, claim_key)


def list_claim_verifications(session: Session) -> list[ClaimVerification]:
    return list(
        session.scalars(select(ClaimVerification).order_by(ClaimVerification.claim_key))
    )


def upsert_claim_verification(
    session: Session,
    claim_key: str,
    *,
    verified_by: str,
    verified_role: str,
    verified_at: datetime,
    verified_by_event_id: str,
) -> None:
    """Plain upsert, like `record_last_seen` -- the latest verification
    always wins, and there is nothing to CAS against (CONTRACTS.md:
    verifying is a review-state marker, not a financial fact)."""
    insert_fn = (
        sqlite_insert if session.get_bind().dialect.name == "sqlite" else pg_insert
    )
    statement = insert_fn(ClaimVerification).values(
        claim_key=claim_key,
        verified_by=verified_by,
        verified_role=verified_role,
        verified_at=verified_at,
        verified_by_event_id=verified_by_event_id,
    )
    statement = statement.on_conflict_do_update(
        index_elements=["claim_key"],
        set_={
            "verified_by": verified_by,
            "verified_role": verified_role,
            "verified_at": verified_at,
            "verified_by_event_id": verified_by_event_id,
        },
    )
    session.execute(statement)
    session.flush()


def delete_claim_verification(session: Session, claim_key: str) -> None:
    existing = get_claim_verification(session, claim_key)
    if existing is not None:
        session.delete(existing)
        session.flush()
