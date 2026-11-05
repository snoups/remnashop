from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("plans", sa.Column("external_squad_new", sa.UUID(), nullable=True))

    op.execute("""
        UPDATE plans
        SET external_squad_new = external_squad[1]
        WHERE external_squad IS NOT NULL;
    """)

    op.drop_column("plans", "external_squad")

    op.alter_column("plans", "external_squad_new", new_column_name="external_squad")


def downgrade() -> None:
    op.add_column("plans", sa.Column("external_squad_new", sa.ARRAY(sa.UUID()), nullable=True))

    op.execute("""
        UPDATE plans
        SET external_squad_new = ARRAY[external_squad]
        WHERE external_squad IS NOT NULL;
    """)

    op.drop_column("plans", "external_squad")

    op.alter_column("plans", "external_squad_new", new_column_name="external_squad")
