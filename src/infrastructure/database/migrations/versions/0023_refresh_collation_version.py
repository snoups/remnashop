from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
