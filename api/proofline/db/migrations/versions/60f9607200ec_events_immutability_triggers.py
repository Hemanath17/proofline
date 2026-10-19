"""events immutability triggers

Revision ID: 60f9607200ec
Revises: b4c6bbd57994
Create Date: 2026-10-18 16:40:49.585444

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "60f9607200ec"
down_revision: str | Sequence[str] | None = "b4c6bbd57994"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Postgres-only: these functions and triggers don't exist on SQLite (used
# only by the offline unit-test fixtures), so immutability there is
# enforced by never calling UPDATE/DELETE from application code, not by a
# database-level guard. The real guard -- the one CONTRACTS.md Storage and
# acceptance test I6 actually require -- is this trigger, proven against a
# real Postgres database in api/tests/pg/test_events_immutable.py.


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        CREATE FUNCTION events_refuse_change() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'events is append-only: % is not allowed', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER events_refuse_update_delete
        BEFORE UPDATE OR DELETE ON events
        FOR EACH ROW EXECUTE FUNCTION events_refuse_change();
        """
    )
    op.execute(
        """
        CREATE TRIGGER events_refuse_truncate
        BEFORE TRUNCATE ON events
        FOR EACH STATEMENT EXECUTE FUNCTION events_refuse_change();
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Dropping the guard, not any data -- safe to reverse.
    op.execute("DROP TRIGGER IF EXISTS events_refuse_truncate ON events;")
    op.execute("DROP TRIGGER IF EXISTS events_refuse_update_delete ON events;")
    op.execute("DROP FUNCTION IF EXISTS events_refuse_change();")
