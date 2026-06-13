from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    promo_audience = postgresql.ENUM(
        "ALL",
        "WITH_ACTIVE_SUBSCRIPTION",
        name="promo_audience",
        create_type=False,
    )
    promo_audience.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "promocodes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("discount_percent", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("audience", sa.Enum("ALL", "WITH_ACTIVE_SUBSCRIPTION", name="promo_audience"), nullable=False),
        sa.Column("max_activations", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('UTC', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('UTC', now())"), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_promocodes_code"), "promocodes", ["code"], unique=True)
    op.create_index(op.f("ix_promocodes_plan_id"), "promocodes", ["plan_id"], unique=False)

    op.create_table(
        "promocode_activations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("promocode_id", sa.Integer(), nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("transaction_payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('UTC', now())"), nullable=False),
        sa.ForeignKeyConstraint(["promocode_id"], ["promocodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_telegram_id"], ["users.telegram_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("promocode_id", "user_telegram_id", name="uq_promo_activation_user"),
    )
    op.create_index(op.f("ix_promocode_activations_promocode_id"), "promocode_activations", ["promocode_id"], unique=False)
    op.create_index(op.f("ix_promocode_activations_user_telegram_id"), "promocode_activations", ["user_telegram_id"], unique=False)

    op.add_column(
        "transactions",
        sa.Column("promocode_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_transactions_promocode_id",
        "transactions",
        "promocodes",
        ["promocode_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_transactions_promocode_id", "transactions", ["promocode_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_transactions_promocode_id", table_name="transactions")
    op.drop_constraint("fk_transactions_promocode_id", "transactions", type_="foreignkey")
    op.drop_column("transactions", "promocode_id")

    op.drop_index(op.f("ix_promocode_activations_user_telegram_id"), table_name="promocode_activations")
    op.drop_index(op.f("ix_promocode_activations_promocode_id"), table_name="promocode_activations")
    op.drop_table("promocode_activations")

    op.drop_index(op.f("ix_promocodes_plan_id"), table_name="promocodes")
    op.drop_index(op.f("ix_promocodes_code"), table_name="promocodes")
    op.drop_table("promocodes")

    op.execute("DROP TYPE IF EXISTS promo_audience")
