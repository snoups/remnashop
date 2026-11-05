from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: Union[str, None] = "0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("device_single_reset_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("device_all_reset_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("link_reset_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("referral_code_reset_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "referral_code_reset_at")
    op.drop_column("subscriptions", "link_reset_at")
    op.drop_column("subscriptions", "device_all_reset_at")
    op.drop_column("subscriptions", "device_single_reset_at")
