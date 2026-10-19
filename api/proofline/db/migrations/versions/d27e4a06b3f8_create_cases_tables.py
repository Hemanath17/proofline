"""create cases, case_proposals and case_decisions tables

Revision ID: d27e4a06b3f8
Revises: c1a53e8f9201
Create Date: 2026-10-18 18:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d27e4a06b3f8"
down_revision: str | Sequence[str] | None = "c1a53e8f9201"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Same JSON-everywhere/JSONB-on-Postgres split as events.payload
# (proofline/db/models.py), so the SQLite test fixtures keep working.
_json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "cases",
        sa.Column("case_id", sa.String(), nullable=False),
        sa.Column("root_cause_key", sa.String(), nullable=False),
        sa.Column("origin", sa.String(), nullable=False),
        sa.Column("origin_ref", sa.String(), nullable=True),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("claims", _json_type, nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("finding_type", sa.String(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("assignee_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("check_id", sa.String(), nullable=True),
        sa.Column("check_version", sa.Integer(), nullable=True),
        sa.Column("evidence_refs", _json_type, nullable=False),
        sa.Column("observed", sa.String(), nullable=True),
        sa.Column("expected", sa.String(), nullable=True),
        sa.Column("limitations", sa.String(), nullable=True),
        sa.Column("recommended_action", sa.String(), nullable=True),
        sa.Column("tax_effect_federal", sa.Numeric(), nullable=True),
        sa.Column("tax_effect_california", sa.Numeric(), nullable=True),
        sa.Column("tax_effect_kind", sa.String(), nullable=True),
        sa.Column("tax_effect_direction", sa.String(), nullable=True),
        sa.Column(
            "impact_unknown", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("cleared_reason", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("case_id"),
    )
    op.create_index("ix_cases_root_cause_key", "cases", ["root_cause_key"], unique=True)

    op.create_table(
        "case_proposals",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("case_id", sa.String(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("resolution_type", sa.String(), nullable=False),
        sa.Column("fields", _json_type, nullable=False),
        sa.Column("evidence_refs", _json_type, nullable=False),
        sa.Column("proposed_by", sa.String(), nullable=False),
        sa.Column("proposed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"]),
    )
    op.create_index("ix_case_proposals_case_id", "case_proposals", ["case_id"])
    op.create_index(
        "ix_case_proposals_case_revision",
        "case_proposals",
        ["case_id", "revision_number"],
        unique=True,
    )

    op.create_table(
        "case_decisions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("case_id", sa.String(), nullable=False),
        sa.Column("proposal_revision", sa.Integer(), nullable=True),
        sa.Column("decision", sa.String(), nullable=False),
        sa.Column("decided_by", sa.String(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"]),
    )
    op.create_index("ix_case_decisions_case_id", "case_decisions", ["case_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_case_decisions_case_id", table_name="case_decisions")
    op.drop_table("case_decisions")
    op.drop_index("ix_case_proposals_case_revision", table_name="case_proposals")
    op.drop_index("ix_case_proposals_case_id", table_name="case_proposals")
    op.drop_table("case_proposals")
    op.drop_index("ix_cases_root_cause_key", table_name="cases")
    op.drop_table("cases")
