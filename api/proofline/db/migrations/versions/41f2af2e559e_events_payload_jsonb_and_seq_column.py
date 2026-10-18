"""events payload jsonb and seq column

Revision ID: 41f2af2e559e
Revises: 8a1aa2459a26
Create Date: 2026-10-18 14:55:54.324509

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "41f2af2e559e"
down_revision: str | Sequence[str] | None = "8a1aa2459a26"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Same JSON content, binary/indexable storage -- existing rows are not
    # rewritten in any way that changes their data, only how it's stored.
    op.alter_column(
        "events",
        "payload",
        type_=postgresql.JSONB(astext_type=sa.Text()),
        postgresql_using="payload::jsonb",
        existing_nullable=False,
    )
    # Postgres requires an identity column to be NOT NULL, and won't let that
    # be relaxed afterwards (confirmed against the real database -- ALTER
    # COLUMN ... DROP NOT NULL is rejected on an identity column). Existing
    # rows get backfilled by the identity sequence automatically when the
    # column is added; new rows always get one too, since the ORM never
    # supplies this column explicitly. SQLite (used by the test fixtures,
    # which has no identity support at all) handles this the same way the
    # model does -- see proofline/db/models.py and proofline/db/repository.py.
    op.add_column(
        "events",
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("events", "seq")
    op.alter_column(
        "events",
        "payload",
        type_=sa.JSON(),
        postgresql_using="payload::json",
        existing_nullable=False,
    )
