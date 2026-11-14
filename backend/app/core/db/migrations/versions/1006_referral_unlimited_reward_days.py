from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "1006"
down_revision: Union[str, None] = "1005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "referral_settings",
        sa.Column("unlimited_reward_days", sa.Integer(), server_default="365", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("referral_settings", "unlimited_reward_days")
