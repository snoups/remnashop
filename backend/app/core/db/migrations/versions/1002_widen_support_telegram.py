from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "1002"
down_revision: Union[str, None] = "1001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "shop_settings",
        "support_telegram",
        existing_type=sa.String(length=32),
        type_=sa.String(length=40),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.execute(
        "UPDATE shop_settings SET support_telegram = left(support_telegram, 32) "
        "WHERE length(support_telegram) > 32"
    )
    op.alter_column(
        "shop_settings",
        "support_telegram",
        existing_type=sa.String(length=40),
        type_=sa.String(length=32),
        existing_nullable=True,
    )
