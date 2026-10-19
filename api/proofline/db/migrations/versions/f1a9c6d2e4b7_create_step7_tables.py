"""create adjustments, sign_offs and document_dispositions tables

Revision ID: f1a9c6d2e4b7
Revises: e94f2c7a518b
Create Date: 2026-10-18 22:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f1a9c6d2e4b7"
down_revision: str | Sequence[str] | None = "e94f2c7a518b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Same JSON-everywhere/JSONB-on-Postgres split as events.payload
# (proofline/db/models.py), so the SQLite test fixtures keep working.
_json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "adjustments",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("claim_key", sa.String(), nullable=False),
        sa.Column("old_value", sa.String(), nullable=False),
        sa.Column("new_value", sa.String(), nullable=False),
        sa.Column("evidence_refs", _json_type, nullable=False),
        sa.Column("case_id", sa.String(), nullable=True),
        sa.Column("decision_id", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"]),
        sa.ForeignKeyConstraint(["decision_id"], ["case_decisions.id"]),
    )
    op.create_index("ix_adjustments_claim_key", "adjustments", ["claim_key"])

    op.create_table(
        "sign_offs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("signed_by", sa.String(), nullable=False),
        sa.Column("signed_role", sa.String(), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("engine_version", sa.String(), nullable=False),
        sa.Column("active_adjustment_ids", _json_type, nullable=False),
        sa.Column("check_run_id", sa.String(), nullable=True),
        sa.Column("evidence_fingerprint", sa.String(), nullable=False),
        sa.Column("values_fingerprint", sa.String(), nullable=False),
        sa.Column("decisions_fingerprint", sa.String(), nullable=False),
        sa.Column("scope_fingerprint", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["check_run_id"], ["check_runs.id"]),
    )
    op.create_index(
        "ix_sign_offs_scope_version", "sign_offs", ["scope", "version"], unique=True
    )

    op.create_table(
        "document_dispositions",
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("disposition", sa.String(), nullable=False, server_default="pending"),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("confirmed_by", sa.String(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("document_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("document_dispositions")
    op.drop_index("ix_sign_offs_scope_version", table_name="sign_offs")
    op.drop_table("sign_offs")
    op.drop_index("ix_adjustments_claim_key", table_name="adjustments")
    op.drop_table("adjustments")
