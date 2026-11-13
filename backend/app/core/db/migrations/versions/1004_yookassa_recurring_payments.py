from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "1004"
down_revision: Union[str, None] = "1003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("recurring_consent", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "transactions",
        sa.Column("is_recurring", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("transactions", sa.Column("saved_payment_method_id", sa.String(), nullable=True))
    op.add_column(
        "transactions", sa.Column("payment_method_shop_id", sa.String(128), nullable=True)
    )
    op.add_column(
        "transactions", sa.Column("yookassa_receipt_vat_code", sa.Integer(), nullable=True)
    )
    op.create_table(
        "recurring_payments",
        sa.Column(
            "subscription_id",
            sa.Integer(),
            sa.ForeignKey("subscriptions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "source_transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=True
        ),
        sa.Column("payment_method_id", sa.String(), nullable=True),
        sa.Column("shop_id", sa.String(128), server_default="", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("customer_disabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(64), nullable=True),
        sa.Column(
            "pending_transaction_id",
            sa.Integer(),
            sa.ForeignKey("transactions.id"),
            unique=True,
            nullable=True,
        ),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_recurring_payments_next_attempt_at", "recurring_payments", ["next_attempt_at"]
    )


def downgrade() -> None:
    op.drop_table("recurring_payments")
    op.drop_column("transactions", "yookassa_receipt_vat_code")
    op.drop_column("transactions", "payment_method_shop_id")
    op.drop_column("transactions", "saved_payment_method_id")
    op.drop_column("transactions", "is_recurring")
    op.drop_column("transactions", "recurring_consent")
