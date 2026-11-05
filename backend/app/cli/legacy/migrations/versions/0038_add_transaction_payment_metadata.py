from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0038"
down_revision: Union[str, None] = "0037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("gateway_display_name", sa.String(), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("payment_method", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("transactions", "payment_method")
    op.drop_column("transactions", "gateway_display_name")
