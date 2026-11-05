from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0034"
down_revision: Union[str, None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TYPE IF EXISTS promocode_reward_type")

    op.execute("""
        CREATE TYPE promocode_reward_type AS ENUM (
            'DURATION', 'TRAFFIC', 'DEVICES',
            'SUBSCRIPTION', 'PERSONAL_DISCOUNT', 'PURCHASE_DISCOUNT'
        )
    """)

    op.execute("""
        CREATE TYPE promocode_availability AS ENUM (
            'ALL', 'NEW', 'EXISTING', 'INVITED'
        )
    """)

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
        sa.Column("plan_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column(
            "availability",
            postgresql.ENUM(name="promocode_availability", create_type=False),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
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
    op.create_index("ix_promocodes_code", "promocodes", ["code"], unique=True)

    op.create_table(
        "promocode_activations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("promocode_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "activated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('UTC', now())"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["promocode_id"],
            ["promocodes.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("promocode_id", "user_id"),
    )
    op.create_index(
        "ix_promocode_activations_promocode_id",
        "promocode_activations",
        ["promocode_id"],
    )
    op.create_index(
        "ix_promocode_activations_user_id",
        "promocode_activations",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_table("promocode_activations")
    op.drop_table("promocodes")
    op.execute("DROP TYPE IF EXISTS promocode_availability")
    op.execute("DROP TYPE IF EXISTS promocode_reward_type")
