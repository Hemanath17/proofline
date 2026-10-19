"""create claim_verifications table

Revision ID: 066bc41a1488
Revises: f1a9c6d2e4b7
Create Date: 2026-10-19 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "066bc41a1488"
down_revision: str | Sequence[str] | None = "f1a9c6d2e4b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "claim_verifications",
        sa.Column("claim_key", sa.String(), nullable=False),
        sa.Column("verified_by", sa.String(), nullable=False),
        sa.Column("verified_role", sa.String(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_by_event_id", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("claim_key"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("claim_verifications")
