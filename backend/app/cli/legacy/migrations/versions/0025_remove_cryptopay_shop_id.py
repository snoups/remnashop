from typing import Sequence, Union

from alembic import op

revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE payment_gateways "
        "SET settings = settings - 'shop_id' "
        "WHERE type = 'CRYPTOPAY' AND settings ? 'shop_id'"
    )


def downgrade() -> None:
    pass
