import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

log = logging.getLogger("alembic.runtime.migration")

# Rows whose user_telegram_id has no matching users.telegram_id cannot be
# backfilled to the new user_id FK and would abort the NOT NULL step below.
# Drop these orphans up front so the migration runs cleanly on legacy data.
_ORPHAN_CLEANUPS: tuple[tuple[str, str], ...] = (
    (
        "transactions",
        "DELETE FROM transactions t WHERE NOT EXISTS "
        "(SELECT 1 FROM users u WHERE u.telegram_id = t.user_telegram_id)",
    ),
    (
        "subscriptions",
        "DELETE FROM subscriptions s WHERE NOT EXISTS "
        "(SELECT 1 FROM users u WHERE u.telegram_id = s.user_telegram_id)",
    ),
    (
        "referrals",
        "DELETE FROM referrals r WHERE "
        "NOT EXISTS (SELECT 1 FROM users u WHERE u.telegram_id = r.referrer_telegram_id) "
        "OR NOT EXISTS (SELECT 1 FROM users u WHERE u.telegram_id = r.referred_telegram_id)",
    ),
    (
        "referral_rewards",
        "DELETE FROM referral_rewards rr WHERE NOT EXISTS "
        "(SELECT 1 FROM users u WHERE u.telegram_id = rr.user_telegram_id)",
    ),
    (
        "broadcast_messages",
        "DELETE FROM broadcast_messages bm WHERE NOT EXISTS "
        "(SELECT 1 FROM users u WHERE u.telegram_id = bm.user_telegram_id)",
    ),
)


def _cleanup_orphans() -> None:
    bind = op.get_bind()
    for table, stmt in _ORPHAN_CLEANUPS:
        result = bind.execute(sa.text(stmt))
        if result.rowcount:
            log.warning("0026: deleted %s orphan row(s) from %s", result.rowcount, table)


def upgrade() -> None:
    _cleanup_orphans()

    # users: web auth fields
    op.add_column("users", sa.Column("email", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("password_hash", sa.String(length=512), nullable=True))
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.add_column(
        "users",
        sa.Column(
            "is_email_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.alter_column("users", "is_email_verified", server_default=None)
    op.add_column("users", sa.Column("pending_email", sa.String(length=255), nullable=True))
    op.add_column(
        "users",
        sa.Column("email_verification_code_hash", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("email_verification_expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    # users: auth_type, telegram_id becomes nullable
    op.alter_column("users", "telegram_id", existing_type=sa.BigInteger(), nullable=True)
    op.add_column(
        "users",
        sa.Column("auth_type", sa.String(length=20), nullable=False, server_default="telegram"),
    )
    op.alter_column("users", "auth_type", server_default=None)

    # user_oauth_providers table
    op.create_table(
        "user_oauth_providers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_id", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.timezone("UTC", sa.func.now()),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.timezone("UTC", sa.func.now()),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "provider", name="uq_user_oauth_providers_user_provider"),
        sa.UniqueConstraint("provider", "provider_id", name="uq_user_oauth_providers_provider_id"),
    )
    op.create_index("ix_user_oauth_providers_user_id", "user_oauth_providers", ["user_id"])

    # transactions
    op.add_column("transactions", sa.Column("user_id", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE transactions t
        SET user_id = u.id
        FROM users u
        WHERE u.telegram_id = t.user_telegram_id
    """)
    op.alter_column("transactions", "user_id", nullable=False)
    op.drop_constraint(
        op.f("transactions_user_telegram_id_fkey"), "transactions", type_="foreignkey"
    )
    op.drop_index("ix_transactions_user_telegram_id", table_name="transactions")
    op.drop_column("transactions", "user_telegram_id")
    op.create_index("ix_transactions_user_id", "transactions", ["user_id"], unique=False)
    op.create_foreign_key(
        op.f("transactions_user_id_fkey"),
        "transactions",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # subscriptions
    op.add_column("subscriptions", sa.Column("user_id", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE subscriptions s
        SET user_id = u.id
        FROM users u
        WHERE u.telegram_id = s.user_telegram_id
    """)
    op.alter_column("subscriptions", "user_id", nullable=False)
    op.drop_constraint(
        op.f("subscriptions_user_telegram_id_fkey"), "subscriptions", type_="foreignkey"
    )
    op.drop_index("ix_subscriptions_user_telegram_id", table_name="subscriptions")
    op.drop_column("subscriptions", "user_telegram_id")
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"], unique=False)
    op.create_foreign_key(
        op.f("subscriptions_user_id_fkey"),
        "subscriptions",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # referrals
    op.add_column("referrals", sa.Column("referrer_id", sa.Integer(), nullable=True))
    op.add_column("referrals", sa.Column("referred_id", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE referrals r
        SET referrer_id = u.id
        FROM users u
        WHERE u.telegram_id = r.referrer_telegram_id
    """)
    op.execute("""
        UPDATE referrals r
        SET referred_id = u.id
        FROM users u
        WHERE u.telegram_id = r.referred_telegram_id
    """)
    op.alter_column("referrals", "referrer_id", nullable=False)
    op.alter_column("referrals", "referred_id", nullable=False)
    op.drop_constraint(op.f("referrals_referrer_telegram_id_fkey"), "referrals", type_="foreignkey")
    op.drop_constraint(op.f("referrals_referred_telegram_id_fkey"), "referrals", type_="foreignkey")
    op.drop_index("ix_referrals_referrer_telegram_id", table_name="referrals")
    op.drop_index("ix_referrals_referred_telegram_id", table_name="referrals")
    op.drop_column("referrals", "referrer_telegram_id")
    op.drop_column("referrals", "referred_telegram_id")
    op.create_index("ix_referrals_referrer_id", "referrals", ["referrer_id"], unique=False)
    op.create_index("ix_referrals_referred_id", "referrals", ["referred_id"], unique=True)
    op.create_foreign_key(
        op.f("referrals_referrer_id_fkey"),
        "referrals",
        "users",
        ["referrer_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        op.f("referrals_referred_id_fkey"),
        "referrals",
        "users",
        ["referred_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # referral_rewards
    op.add_column("referral_rewards", sa.Column("user_id", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE referral_rewards rr
        SET user_id = u.id
        FROM users u
        WHERE u.telegram_id = rr.user_telegram_id
    """)
    op.alter_column("referral_rewards", "user_id", nullable=False)
    op.drop_constraint(
        op.f("referral_rewards_user_telegram_id_fkey"), "referral_rewards", type_="foreignkey"
    )
    op.drop_index("ix_referral_rewards_user_telegram_id", table_name="referral_rewards")
    op.drop_column("referral_rewards", "user_telegram_id")
    op.create_index("ix_referral_rewards_user_id", "referral_rewards", ["user_id"], unique=False)
    op.create_foreign_key(
        op.f("referral_rewards_user_id_fkey"),
        "referral_rewards",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # broadcast_messages
    op.add_column("broadcast_messages", sa.Column("user_id", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE broadcast_messages bm
        SET user_id = u.id
        FROM users u
        WHERE u.telegram_id = bm.user_telegram_id
    """)
    op.alter_column("broadcast_messages", "user_id", nullable=False)
    op.drop_index("ix_broadcast_messages_user_telegram_id", table_name="broadcast_messages")
    op.create_index(
        "ix_broadcast_messages_user_id", "broadcast_messages", ["user_id"], unique=False
    )
    op.create_foreign_key(
        op.f("broadcast_messages_user_id_fkey"),
        "broadcast_messages",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.alter_column(
        "broadcast_messages",
        "user_telegram_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )


def downgrade() -> None:
    # broadcast_messages
    op.alter_column(
        "broadcast_messages",
        "user_telegram_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.drop_constraint(
        op.f("broadcast_messages_user_id_fkey"), "broadcast_messages", type_="foreignkey"
    )
    op.drop_index("ix_broadcast_messages_user_id", table_name="broadcast_messages")
    op.drop_column("broadcast_messages", "user_id")
    op.create_index(
        "ix_broadcast_messages_user_telegram_id",
        "broadcast_messages",
        ["user_telegram_id"],
        unique=False,
    )

    # referral_rewards
    op.add_column(
        "referral_rewards",
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=True),
    )
    op.execute("""
        UPDATE referral_rewards rr
        SET user_telegram_id = u.telegram_id
        FROM users u
        WHERE u.id = rr.user_id
    """)
    op.alter_column("referral_rewards", "user_telegram_id", nullable=False)
    op.drop_constraint(
        op.f("referral_rewards_user_id_fkey"), "referral_rewards", type_="foreignkey"
    )
    op.drop_index("ix_referral_rewards_user_id", table_name="referral_rewards")
    op.drop_column("referral_rewards", "user_id")
    op.create_index(
        "ix_referral_rewards_user_telegram_id",
        "referral_rewards",
        ["user_telegram_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("referral_rewards_user_telegram_id_fkey"),
        "referral_rewards",
        "users",
        ["user_telegram_id"],
        ["telegram_id"],
    )

    # referrals
    op.add_column("referrals", sa.Column("referrer_telegram_id", sa.BigInteger(), nullable=True))
    op.add_column("referrals", sa.Column("referred_telegram_id", sa.BigInteger(), nullable=True))
    op.execute("""
        UPDATE referrals r
        SET referrer_telegram_id = u.telegram_id
        FROM users u
        WHERE u.id = r.referrer_id
    """)
    op.execute("""
        UPDATE referrals r
        SET referred_telegram_id = u.telegram_id
        FROM users u
        WHERE u.id = r.referred_id
    """)
    op.alter_column("referrals", "referrer_telegram_id", nullable=False)
    op.alter_column("referrals", "referred_telegram_id", nullable=False)
    op.drop_constraint(op.f("referrals_referrer_id_fkey"), "referrals", type_="foreignkey")
    op.drop_constraint(op.f("referrals_referred_id_fkey"), "referrals", type_="foreignkey")
    op.drop_index("ix_referrals_referrer_id", table_name="referrals")
    op.drop_index("ix_referrals_referred_id", table_name="referrals")
    op.drop_column("referrals", "referrer_id")
    op.drop_column("referrals", "referred_id")
    op.create_index(
        "ix_referrals_referrer_telegram_id", "referrals", ["referrer_telegram_id"], unique=False
    )
    op.create_index(
        "ix_referrals_referred_telegram_id", "referrals", ["referred_telegram_id"], unique=True
    )
    op.create_foreign_key(
        op.f("referrals_referrer_telegram_id_fkey"),
        "referrals",
        "users",
        ["referrer_telegram_id"],
        ["telegram_id"],
    )
    op.create_foreign_key(
        op.f("referrals_referred_telegram_id_fkey"),
        "referrals",
        "users",
        ["referred_telegram_id"],
        ["telegram_id"],
    )

    # subscriptions
    op.add_column("subscriptions", sa.Column("user_telegram_id", sa.BigInteger(), nullable=True))
    op.execute("""
        UPDATE subscriptions s
        SET user_telegram_id = u.telegram_id
        FROM users u
        WHERE u.id = s.user_id
    """)
    op.alter_column("subscriptions", "user_telegram_id", nullable=False)
    op.drop_constraint(op.f("subscriptions_user_id_fkey"), "subscriptions", type_="foreignkey")
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_column("subscriptions", "user_id")
    op.create_index(
        "ix_subscriptions_user_telegram_id", "subscriptions", ["user_telegram_id"], unique=False
    )
    op.create_foreign_key(
        op.f("subscriptions_user_telegram_id_fkey"),
        "subscriptions",
        "users",
        ["user_telegram_id"],
        ["telegram_id"],
        ondelete="CASCADE",
    )

    # transactions
    op.add_column("transactions", sa.Column("user_telegram_id", sa.BigInteger(), nullable=True))
    op.execute("""
        UPDATE transactions t
        SET user_telegram_id = u.telegram_id
        FROM users u
        WHERE u.id = t.user_id
    """)
    op.alter_column("transactions", "user_telegram_id", nullable=False)
    op.drop_constraint(op.f("transactions_user_id_fkey"), "transactions", type_="foreignkey")
    op.drop_index("ix_transactions_user_id", table_name="transactions")
    op.drop_column("transactions", "user_id")
    op.create_index(
        "ix_transactions_user_telegram_id", "transactions", ["user_telegram_id"], unique=False
    )
    op.create_foreign_key(
        op.f("transactions_user_telegram_id_fkey"),
        "transactions",
        "users",
        ["user_telegram_id"],
        ["telegram_id"],
    )

    # user_oauth_providers table
    op.drop_index("ix_user_oauth_providers_user_id", table_name="user_oauth_providers")
    op.drop_table("user_oauth_providers")

    # users: auth_type + telegram_id
    op.drop_column("users", "auth_type")
    op.alter_column("users", "telegram_id", existing_type=sa.BigInteger(), nullable=False)

    # users: web auth fields
    op.drop_column("users", "email_verification_expires_at")
    op.drop_column("users", "email_verification_code_hash")
    op.drop_column("users", "pending_email")
    op.drop_column("users", "is_email_verified")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_column("users", "password_hash")
    op.drop_column("users", "email")
