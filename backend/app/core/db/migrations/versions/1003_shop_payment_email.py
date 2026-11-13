from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "1003"
down_revision: Union[str, None] = "1002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("shop_settings", sa.Column("payment_email", sa.String(length=320), nullable=True))


def downgrade() -> None:
    op.drop_column("shop_settings", "payment_email")
