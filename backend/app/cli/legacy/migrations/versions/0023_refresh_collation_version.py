from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Refreshes the database collation version after a glibc upgrade caused a
    # collation version mismatch (Postgres warns and may reject index operations).
    # This writes directly to the pg_catalog system table, so it REQUIRES a
    # superuser role; without those privileges the migration will fail with a
    # permission error. Idempotent (sets datcollversion to NULL) and has no
    # downgrade — the version is re-derived by Postgres on the next collation use.
    bind = op.get_bind()
    bind.execute(sa.text("SET allow_system_table_mods = on"))
    bind.execute(
        sa.text(
            "UPDATE pg_catalog.pg_database SET datcollversion = NULL"
            " WHERE datname = current_database()"
        )
    )


def downgrade() -> None:
    pass
