from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    campaign_status = postgresql.ENUM(
        "DRAFT",
        "ACTIVE",
        "COMPLETED",
        "ARCHIVED",
        name="giveaway_campaign_status",
        create_type=False,
    )
    entry_status = postgresql.ENUM(
        "ELIGIBLE",
        "WINNER",
        "ARCHIVED",
        "EXCLUDED",
        name="giveaway_entry_status",
        create_type=False,
    )
    purchase_type = postgresql.ENUM(
        "NEW",
        "RENEW",
        "CHANGE",
        name="purchase_type",
        create_type=False,
    )
    campaign_status.create(op.get_bind(), checkfirst=True)
    entry_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "giveaway_campaigns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("status", campaign_status, nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("winner_count", sa.Integer(), nullable=False),
        sa.Column("prize_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("eligible_plan_id", sa.Integer(), nullable=False),
        sa.Column("eligible_duration_days", sa.Integer(), nullable=False),
        sa.Column("eligible_purchase_types", postgresql.JSONB(), nullable=False),
        sa.Column("code_prefix", sa.String(length=8), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "ends_at > starts_at",
            name="ck_giveaway_campaign_period",
        ),
        sa.CheckConstraint(
            "prize_amount >= 0",
            name="ck_giveaway_campaign_prize_amount",
        ),
        sa.CheckConstraint(
            "winner_count > 0",
            name="ck_giveaway_campaign_winner_count",
        ),
        sa.ForeignKeyConstraint(
            ["eligible_plan_id"],
            ["plans.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_giveaway_campaigns_status",
        "giveaway_campaigns",
        ["status"],
    )
    op.create_index(
        "ix_giveaway_campaigns_starts_at",
        "giveaway_campaigns",
        ["starts_at"],
    )
    op.create_index(
        "ix_giveaway_campaigns_ends_at",
        "giveaway_campaigns",
        ["ends_at"],
    )
    op.create_index(
        "ix_giveaway_campaigns_eligible_plan_id",
        "giveaway_campaigns",
        ["eligible_plan_id"],
    )

    op.create_table(
        "giveaway_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_username", sa.String(length=32), nullable=True),
        sa.Column("participant_code", sa.String(length=32), nullable=False),
        sa.Column("transaction_payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("plan_name", sa.String(length=128), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("purchase_type", purchase_type, nullable=False),
        sa.Column("phone", sa.String(length=15), nullable=True),
        sa.Column("status", entry_status, nullable=False),
        sa.Column("winner_rank", sa.Integer(), nullable=True),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "winner_rank IS NULL OR winner_rank > 0",
            name="ck_giveaway_entry_winner_rank",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["giveaway_campaigns.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_telegram_id"],
            ["users.telegram_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "campaign_id",
            "participant_code",
            name="uq_giveaway_entry_campaign_code",
        ),
        sa.UniqueConstraint(
            "campaign_id",
            "winner_rank",
            name="uq_giveaway_entry_campaign_winner_rank",
        ),
        sa.UniqueConstraint(
            "transaction_payment_id",
            name="uq_giveaway_entry_transaction_payment",
        ),
    )
    op.create_index(
        "ix_giveaway_entries_campaign_id",
        "giveaway_entries",
        ["campaign_id"],
    )
    op.create_index(
        "ix_giveaway_entries_user_telegram_id",
        "giveaway_entries",
        ["user_telegram_id"],
    )
    op.create_index(
        "ix_giveaway_entries_status",
        "giveaway_entries",
        ["status"],
    )
    op.create_index(
        "ix_giveaway_entries_transaction_payment_id",
        "giveaway_entries",
        ["transaction_payment_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_giveaway_entries_transaction_payment_id",
        table_name="giveaway_entries",
    )
    op.drop_index("ix_giveaway_entries_status", table_name="giveaway_entries")
    op.drop_index("ix_giveaway_entries_user_telegram_id", table_name="giveaway_entries")
    op.drop_index("ix_giveaway_entries_campaign_id", table_name="giveaway_entries")
    op.drop_table("giveaway_entries")

    op.drop_index(
        "ix_giveaway_campaigns_eligible_plan_id",
        table_name="giveaway_campaigns",
    )
    op.drop_index("ix_giveaway_campaigns_ends_at", table_name="giveaway_campaigns")
    op.drop_index("ix_giveaway_campaigns_starts_at", table_name="giveaway_campaigns")
    op.drop_index("ix_giveaway_campaigns_status", table_name="giveaway_campaigns")
    op.drop_table("giveaway_campaigns")

    op.execute("DROP TYPE IF EXISTS giveaway_entry_status")
    op.execute("DROP TYPE IF EXISTS giveaway_campaign_status")
