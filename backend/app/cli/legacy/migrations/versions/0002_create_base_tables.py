from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_gateways",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column(
            "type", postgresql.ENUM(name="payment_gateway_type", create_type=False), nullable=False
        ),
        sa.Column("currency", postgresql.ENUM(name="currency", create_type=False), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("settings", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("type"),
    )

    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rules_required", sa.Boolean(), nullable=False),
        sa.Column("channel_required", sa.Boolean(), nullable=False),
        sa.Column("rules_link", sa.String(), nullable=False),
        sa.Column("channel_link", sa.String(), nullable=False),
        sa.Column(
            "access_mode", postgresql.ENUM(name="access_mode", create_type=False), nullable=False
        ),
        sa.Column(
            "default_currency", postgresql.ENUM(name="currency", create_type=False), nullable=False
        ),
        sa.Column("user_notifications", sa.JSON(), nullable=True),
        sa.Column("system_notifications", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "promocodes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "reward_type",
            postgresql.ENUM(name="promocode_reward_type", create_type=False),
            nullable=False,
        ),
        sa.Column("reward", sa.Integer(), nullable=True),
        sa.Column("plan", sa.JSON(), nullable=True),
        sa.Column("lifetime", sa.Integer(), nullable=True),
        sa.Column("max_activations", sa.Integer(), nullable=True),
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
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("type", postgresql.ENUM(name="plan_type", create_type=False), nullable=False),
        sa.Column(
            "availability",
            postgresql.ENUM(name="plan_availability", create_type=False),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("traffic_limit", sa.Integer(), nullable=False),
        sa.Column("device_limit", sa.Integer(), nullable=False),
        sa.Column("allowed_user_ids", sa.ARRAY(sa.BigInteger()), nullable=True),
        sa.Column("internal_squads", sa.ARRAY(sa.UUID()), nullable=False),
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
        sa.UniqueConstraint("name"),
    )


def downgrade() -> None:
    op.drop_table("plans")
    op.drop_table("promocodes")
    op.drop_table("settings")
    op.drop_table("payment_gateways")
