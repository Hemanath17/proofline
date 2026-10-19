from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import Uuid

# JSONB on Postgres (indexable, binary storage); plain JSON everywhere else,
# so the SQLite-backed test fixtures keep working unchanged.
_JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


def _iso(value: datetime | None) -> str | None:
    """SQLite's DateTime type doesn't reliably round-trip whether a stored
    timestamp was timezone-aware, so a value read back from it can come
    back naive even though every timestamp here is written as UTC --
    treating a naive value as UTC here means `to_dict()` compares the same
    whether or not this particular read happened to go through SQLite."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


class Base(DeclarativeBase):
    pass


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_entity", "entity_type", "entity_id"),
        Index("ix_events_seq", "seq"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(_JSON_TYPE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Postgres always fills this from its own identity sequence -- the ORM
    # never supplies it explicitly. SQLite has no equivalent mechanism, so
    # repository.insert_event() assigns a placeholder there; see its
    # comment for why that's safe.
    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=False), nullable=False)
    # Added in Step 4. Nullable so the Step 1 proof-of-deploy row, which
    # predates all of these, stays valid -- every event written through the
    # action service from here on supplies all five.
    actor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String, nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # The entity's revision *after* this event is applied -- None for
    # log-only events (e.g. revealing a sensitive value) that have no
    # current-state row to version.
    revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Business time: when the action happened, as opposed to `created_at`
    # (record time: when we wrote it down). They differ during a replay
    # (Step 8), where an action is recorded today for something that
    # happened on the packet's timeline months ago.
    occurred_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ReviewNote(Base):
    """Current state for one review note. The note's own thread of
    responses lives only in events (`review_note_responded`) -- a growing
    log of "what people did" isn't a point-in-time snapshot, so it has no
    column here; `respond_review_note` still bumps `revision` to serialize
    concurrent writers."""

    __tablename__ = "review_notes"
    __table_args__ = (Index("ix_review_notes_about", "about_type", "about_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    about_type: Mapped[str] = mapped_column(String, nullable=False)
    about_id: Mapped[str] = mapped_column(String, nullable=False)
    opened_by: Mapped[str] = mapped_column(String, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    resolved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution: Mapped[str | None] = mapped_column(String, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    def to_dict(self) -> dict:
        """The one place this shape is written -- shared by the
        review-notes routes and the 409 handler for a stale revision, so
        they can never drift apart."""
        return {
            "id": self.id,
            "about_type": self.about_type,
            "about_id": self.about_id,
            "opened_by": self.opened_by,
            "opened_at": _iso(self.opened_at),
            "status": self.status,
            "resolved_by": self.resolved_by,
            "resolved_at": _iso(self.resolved_at),
            "resolution": self.resolution,
            "revision": self.revision,
        }


class CheckRun(Base):
    """An append-only snapshot of the findings at a decision point. Never
    updated -- `record_check_run` only ever inserts a new row."""

    __tablename__ = "check_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("events.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    return_version: Mapped[str] = mapped_column(String, nullable=False)
    findings: Mapped[list] = mapped_column(_JSON_TYPE, nullable=False)
    failures: Mapped[list] = mapped_column(_JSON_TYPE, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "return_version": self.return_version,
            "findings": self.findings,
            "failures": self.failures,
        }
