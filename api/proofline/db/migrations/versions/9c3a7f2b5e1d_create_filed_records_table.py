"""create filed_records table, with its own immutability triggers

Revision ID: 9c3a7f2b5e1d
Revises: 066bc41a1488
Create Date: 2026-10-19 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c3a7f2b5e1d"
down_revision: str | Sequence[str] | None = "066bc41a1488"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Same Postgres-only caveat as 60f9607200ec (events' own immutability
# triggers): the trigger function and triggers below don't exist on
# SQLite, used only by the offline unit-test fixtures. The real guard --
# the one CONTRACTS.md Storage and acceptance test I6 require for the
# filed record -- is proven against a real Postgres database in
# api/tests/pg/test_filed_records_immutable.py.
#
# `jurisdiction` is unique, not just indexed: nothing in this step builds
# amendments (CONTRACTS.md C5 says that's a new package pointing at the
# filed record it amends -- Step 9+), so today exactly one filed record
# per jurisdiction is correct, and the unique index is what turns two
# concurrent "accept this filing" calls for the same jurisdiction into a
# clean action-service conflict instead of two filed records racing into
# existence (same race class, and the same fix shape, as `sign_offs`'s
# own (scope, version) unique index). A later step that actually builds
# amendments drops this constraint in its own migration.


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "filed_records",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("jurisdiction", sa.String(), nullable=False),
        sa.Column("package_reference", sa.String(), nullable=False),
        sa.Column("amounts_fingerprint", sa.String(), nullable=False),
        sa.Column("identity_fingerprint", sa.String(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submission_event_id", sa.Uuid(), nullable=False),
        sa.Column("amends_filed_record_id", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["submission_event_id"], ["events.id"]),
        sa.ForeignKeyConstraint(["amends_filed_record_id"], ["filed_records.id"]),
    )
    op.create_index(
        "ix_filed_records_jurisdiction", "filed_records", ["jurisdiction"], unique=True
    )
    op.execute(
        """
        CREATE FUNCTION filed_records_refuse_change() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'filed_records is append-only: % is not allowed', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER filed_records_refuse_update_delete
        BEFORE UPDATE OR DELETE ON filed_records
        FOR EACH ROW EXECUTE FUNCTION filed_records_refuse_change();
        """
    )
    op.execute(
        """
        CREATE TRIGGER filed_records_refuse_truncate
        BEFORE TRUNCATE ON filed_records
        FOR EACH STATEMENT EXECUTE FUNCTION filed_records_refuse_change();
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER IF EXISTS filed_records_refuse_truncate ON filed_records;")
    op.execute(
        "DROP TRIGGER IF EXISTS filed_records_refuse_update_delete ON filed_records;"
    )
    op.execute("DROP FUNCTION IF EXISTS filed_records_refuse_change();")
    op.drop_index("ix_filed_records_jurisdiction", table_name="filed_records")
    op.drop_table("filed_records")
