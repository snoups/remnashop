from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "1004"
down_revision: Union[str, None] = "1003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 10 places: 1/85 kept as 0.0117647059 switches the anchor back to 85.000000, not 84.997875
    op.alter_column(
        "currency_rates",
        "rate",
        type_=sa.Numeric(16, 10),
        existing_type=sa.Numeric(12, 6),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "currency_rates",
        "rate",
        type_=sa.Numeric(12, 6),
        existing_type=sa.Numeric(16, 10),
        existing_nullable=False,
    )
