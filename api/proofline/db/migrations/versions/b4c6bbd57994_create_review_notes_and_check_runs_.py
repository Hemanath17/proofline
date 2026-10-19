"""create review notes and check runs tables

Revision ID: b4c6bbd57994
Revises: 7e12e0496083
Create Date: 2026-10-18 16:40:49.331890

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b4c6bbd57994"
down_revision: str | Sequence[str] | None = "7e12e0496083"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Same JSON-everywhere/JSONB-on-Postgres split as events.payload
# (proofline/db/models.py), so the SQLite test fixtures keep working.
_json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "review_notes",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("about_type", sa.String(), nullable=False),
        sa.Column("about_id", sa.String(), nullable=False),
        sa.Column("opened_by", sa.String(), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("resolved_by", sa.String(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution", sa.String(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_notes_about", "review_notes", ["about_type", "about_id"])
    op.create_table(
        "check_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("return_version", sa.String(), nullable=False),
        sa.Column("findings", _json_type, nullable=False),
        sa.Column("failures", _json_type, nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("check_runs")
    op.drop_index("ix_review_notes_about", table_name="review_notes")
    op.drop_table("review_notes")
