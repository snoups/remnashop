from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plan_prices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("currency", postgresql.ENUM(name="currency", create_type=False), nullable=False),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("plan_duration_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["plan_duration_id"], ["plan_durations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("plan_prices")
