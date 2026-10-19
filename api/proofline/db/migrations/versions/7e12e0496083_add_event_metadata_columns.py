"""add event metadata columns

Revision ID: 7e12e0496083
Revises: 41f2af2e559e
Create Date: 2026-10-18 16:40:45.952917

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7e12e0496083"
down_revision: str | Sequence[str] | None = "41f2af2e559e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # All nullable: the Step 1 proof-of-deploy row predates every one of
    # these and must stay valid. Every event written through the action
    # service from Step 4 on supplies all five.
    op.add_column("events", sa.Column("actor_id", sa.String(), nullable=True))
    op.add_column("events", sa.Column("entity_type", sa.String(), nullable=True))
    op.add_column("events", sa.Column("entity_id", sa.String(), nullable=True))
    op.add_column("events", sa.Column("revision", sa.Integer(), nullable=True))
    op.add_column(
        "events", sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index("ix_events_entity", "events", ["entity_type", "entity_id"])
    op.create_index("ix_events_seq", "events", ["seq"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_events_seq", table_name="events")
    op.drop_index("ix_events_entity", table_name="events")
    op.drop_column("events", "occurred_at")
    op.drop_column("events", "revision")
    op.drop_column("events", "entity_id")
    op.drop_column("events", "entity_type")
    op.drop_column("events", "actor_id")
