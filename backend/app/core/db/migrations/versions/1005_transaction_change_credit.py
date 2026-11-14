from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "1005"
down_revision: Union[str, None] = "1004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column(
            "change_credit",
            sa.Numeric(precision=10, scale=2),
            server_default="0",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("transactions", "change_credit")
