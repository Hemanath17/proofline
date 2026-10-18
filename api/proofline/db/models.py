from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Identity, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import Uuid

# JSONB on Postgres (indexable, binary storage); plain JSON everywhere else,
# so the SQLite-backed test fixtures keep working unchanged.
_JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class Event(Base):
    __tablename__ = "events"

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
