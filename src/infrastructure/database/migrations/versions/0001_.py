from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_code", sa.String(), unique=True, index=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("tag", sa.String(), nullable=True),
        sa.Column(
            "type",
            sa.Enum("TRAFFIC", "DEVICES", "BOTH", "UNLIMITED", name="plan_type"),
            nullable=False,
        ),
        sa.Column(
            "availability",
            sa.Enum(
                "ALL", "NEW", "EXISTING", "INVITED", "ALLOWED", "LINK", name="plan_availability"
            ),
            nullable=False,
        ),
        sa.Column(
            "traffic_limit_strategy",
            sa.Enum("NO_RESET", "DAY", "WEEK", "MONTH", name="traffic_limit_strategy"),
            nullable=False,
        ),
        sa.Column("traffic_limit", sa.Integer(), nullable=True),
        sa.Column("device_limit", sa.Integer(), nullable=True),
        sa.Column("allowed_user_ids", sa.ARRAY(sa.BigInteger()), nullable=False),
        sa.Column("internal_squads", sa.ARRAY(sa.UUID()), nullable=False),
        sa.Column("external_squad", sa.UUID(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_trial", sa.Boolean(), nullable=False),
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
    )
    op.create_index(op.f("ix_plans_name"), "plans", ["name"], unique=True)

    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "default_currency", sa.Enum("USD", "XTR", "RUB", name="currency"), nullable=False
        ),
        sa.Column("access", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("requirements", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("notifications", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("referral", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=32), nullable=True),
        sa.Column("referral_code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column(
            "role",
            sa.Enum("USER", "PREVIEW", "ADMIN", "DEV", "OWNER", "SYSTEM", name="user_role"),
            nullable=False,
        ),
        sa.Column(
            "language",
            sa.Enum(
                "AR",
                "AZ",
                "BE",
                "CS",
                "DE",
                "EN",
                "ES",
                "FA",
                "FR",
                "HE",
                "HI",
                "ID",
                "IT",
                "JA",
                "KK",
                "KO",
                "MS",
                "NL",
                "PL",
                "PT",
                "RO",
                "RU",
                "SR",
                "TR",
                "UK",
                "UZ",
                "VI",
                name="locale",
            ),
            nullable=False,
        ),
        sa.Column("personal_discount", sa.Integer(), nullable=False),
        sa.Column("purchase_discount", sa.Integer(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("is_blocked", sa.Boolean(), nullable=False),
        sa.Column("is_bot_blocked", sa.Boolean(), nullable=False),
        sa.Column("is_rules_accepted", sa.Boolean(), nullable=False),
        sa.Column("is_trial_available", sa.Boolean(), nullable=False),
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
        sa.UniqueConstraint("telegram_id", name="uq_users_telegram_id"),
    )
    op.create_index(op.f("ix_users_referral_code"), "users", ["referral_code"], unique=True)
    op.create_index(op.f("ix_users_telegram_id"), "users", ["telegram_id"], unique=True)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=False)

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_remna_id", sa.UUID(), nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "ACTIVE", "DISABLED", "LIMITED", "EXPIRED", "DELETED", name="subscription_status"
            ),
            nullable=False,
        ),
        sa.Column("is_trial", sa.Boolean(), nullable=False),
        sa.Column("traffic_limit", sa.Integer(), nullable=False),
        sa.Column("device_limit", sa.Integer(), nullable=False),
        sa.Column(
            "traffic_limit_strategy",
            sa.Enum("NO_RESET", "DAY", "WEEK", "MONTH", name="traffic_limit_strategy"),
            nullable=False,
        ),
        sa.Column("tag", sa.String(), nullable=True),
        sa.Column("internal_squads", sa.ARRAY(sa.UUID()), nullable=False),
        sa.Column("external_squad", sa.UUID(), nullable=True),
        sa.Column("expire_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("plan_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
    )
    op.create_index(
        op.f("ix_subscriptions_user_remna_id"), "subscriptions", ["user_remna_id"], unique=False
    )
    op.create_index(
        op.f("ix_subscriptions_user_telegram_id"),
        "subscriptions",
        ["user_telegram_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_users_current_subscription",
        "users",
        "subscriptions",
        ["current_subscription_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_subscriptions_user",
        "subscriptions",
        "users",
        ["user_telegram_id"],
        ["telegram_id"],
        ondelete="CASCADE",
    )

    op.create_table(
        "plan_durations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "referrals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("referrer_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("referred_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("level", sa.Enum("FIRST", "SECOND", name="referral_level"), nullable=False),
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
        sa.ForeignKeyConstraint(["referred_telegram_id"], ["users.telegram_id"]),
        sa.ForeignKeyConstraint(["referrer_telegram_id"], ["users.telegram_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("payment_id", sa.UUID(), nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING", "COMPLETED", "CANCELED", "REFUNDED", "FAILED", name="transaction_status"
            ),
            nullable=False,
        ),
        sa.Column("is_test", sa.Boolean(), nullable=False),
        sa.Column(
            "purchase_type", sa.Enum("NEW", "RENEW", "CHANGE", name="purchase_type"), nullable=False
        ),
        sa.Column(
            "gateway_type",
            sa.Enum(
                "TELEGRAM_STARS",
                "YOOKASSA",
                "YOOMONEY",
                "CRYPTOMUS",
                "HELEKET",
                "CRYPTOPAY",
                "ROBOKASSA",
                name="payment_gateway_type",
            ),
            nullable=False,
        ),
        sa.Column("pricing", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("currency", sa.Enum("USD", "XTR", "RUB", name="currency"), nullable=False),
        sa.Column("plan_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
    )
    op.create_index(op.f("ix_transactions_payment_id"), "transactions", ["payment_id"], unique=True)
    op.create_index(
        op.f("ix_transactions_user_telegram_id"), "transactions", ["user_telegram_id"], unique=False
    )

    op.create_table(
        "plan_prices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_duration_id", sa.Integer(), nullable=False),
        sa.Column("currency", sa.Enum("USD", "XTR", "RUB", name="currency"), nullable=False),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.ForeignKeyConstraint(["plan_duration_id"], ["plan_durations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "referral_rewards",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("referral_id", sa.Integer(), nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "type", sa.Enum("POINTS", "EXTRA_DAYS", name="referral_reward_type"), nullable=False
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("is_issued", sa.Boolean(), nullable=False),
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
        sa.ForeignKeyConstraint(["referral_id"], ["referrals.id"]),
        sa.ForeignKeyConstraint(["user_telegram_id"], ["users.telegram_id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_current_subscription", "users", type_="foreignkey")
    op.drop_constraint("fk_subscriptions_user", "subscriptions", type_="foreignkey")

    op.drop_table("referral_rewards")
    op.drop_table("plan_prices")
    op.drop_index(op.f("ix_transactions_user_telegram_id"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_payment_id"), table_name="transactions")
    op.drop_table("transactions")
    op.drop_table("referrals")
    op.drop_table("plan_durations")
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_telegram_id"), table_name="users")
    op.drop_index(op.f("ix_users_referral_code"), table_name="users")
    op.drop_table("users")
    op.drop_index(op.f("ix_subscriptions_user_telegram_id"), table_name="subscriptions")
    op.drop_index(op.f("ix_subscriptions_user_remna_id"), table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_table("settings")
    op.drop_index(op.f("ix_plans_name"), table_name="plans")
    op.drop_table("plans")
