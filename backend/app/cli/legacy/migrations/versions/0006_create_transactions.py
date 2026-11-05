from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("payment_id", sa.UUID(), nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(name="transaction_status", create_type=False),
            nullable=False,
        ),
        sa.Column("is_test", sa.Boolean(), nullable=False),
        sa.Column(
            "purchase_type", postgresql.ENUM(name="purchasetype", create_type=False), nullable=False
        ),
        sa.Column(
            "gateway_type",
            postgresql.ENUM(name="payment_gateway_type", create_type=False),
            nullable=False,
        ),
        sa.Column("pricing", sa.JSON(), nullable=False),
        sa.Column("currency", postgresql.ENUM(name="currency", create_type=False), nullable=False),
        sa.Column("plan", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('UTC', now())"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('UTC', now())"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_telegram_id"], ["users.telegram_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_id"),
    )


def downgrade() -> None:
    op.drop_table("transactions")
