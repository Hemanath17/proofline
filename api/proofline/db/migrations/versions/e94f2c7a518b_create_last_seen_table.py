"""create last_seen table

Revision ID: e94f2c7a518b
Revises: d27e4a06b3f8
Create Date: 2026-10-18 18:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e94f2c7a518b"
down_revision: str | Sequence[str] | None = "d27e4a06b3f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema. Plain UI state (docs/UX.md "Since you last looked"),
    not a workpaper event -- no immutability trigger."""
    op.create_table(
        "last_seen",
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("actor_id", "entity_type", "entity_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("last_seen")
