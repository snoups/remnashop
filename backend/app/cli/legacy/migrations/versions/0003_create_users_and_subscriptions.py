from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("role", postgresql.ENUM(name="user_role", create_type=False), nullable=False),
        sa.Column("language", postgresql.ENUM(name="locale", create_type=False), nullable=False),
        sa.Column("personal_discount", sa.Integer(), nullable=False),
        sa.Column("purchase_discount", sa.Integer(), nullable=False),
        sa.Column("is_blocked", sa.Boolean(), nullable=False),
        sa.Column("is_bot_blocked", sa.Boolean(), nullable=False),
        sa.Column("current_subscription_id", sa.Integer(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_id"),
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_remna_id", sa.UUID(), nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(name="subscription_status", create_type=False),
            nullable=False,
        ),
        sa.Column("is_trial", sa.Boolean(), nullable=False),
        sa.Column("traffic_limit", sa.Integer(), nullable=False),
        sa.Column("device_limit", sa.Integer(), nullable=False),
        sa.Column("internal_squads", sa.ARRAY(sa.UUID()), nullable=False),
        sa.Column("expire_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
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
        sa.ForeignKeyConstraint(["user_telegram_id"], ["users.telegram_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_subscriptions_user_telegram_id"),
        "subscriptions",
        ["user_telegram_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_users_current_subscription_id",
        "users",
        "subscriptions",
        ["current_subscription_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_current_subscription_id", "users", type_="foreignkey")
    op.drop_index(op.f("ix_subscriptions_user_telegram_id"), table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_table("users")
