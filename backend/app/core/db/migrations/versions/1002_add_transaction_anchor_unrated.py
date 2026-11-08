from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "1002"
down_revision: Union[str, None] = "1001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("anchor_unrated", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("transactions", "anchor_unrated")
