"""add review_notes.body column

Revision ID: c1a53e8f9201
Revises: 60f9607200ec
Create Date: 2026-10-18 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1a53e8f9201"
down_revision: str | Sequence[str] | None = "60f9607200ec"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("review_notes", sa.Column("body", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("review_notes", "body")
