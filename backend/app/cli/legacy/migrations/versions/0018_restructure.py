import hashlib
import string
from typing import Final, Sequence, Union

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ALPHABET: Final[str] = string.ascii_letters + string.digits


def _base62_encode(number: int) -> str:
    if number == 0:
        return _ALPHABET[0]

    arr = []
    base = len(_ALPHABET)
    temp_number = number

    while temp_number:
        temp_number, rem = divmod(temp_number, base)
        arr.append(_ALPHABET[rem])

    arr.reverse()
    result = "".join(arr)
    return result


def _generate_public_code(plan_id: int, crypt_key: str, length: int = 8) -> str:
    payload = f"{plan_id}:{crypt_key}"
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    code_int = int.from_bytes(digest[:6], "big")
    full_code = _base62_encode(code_int)
    return full_code[:length].rjust(length, "0")


def upgrade() -> None:
    conn = op.get_bind()
    ctx = context.get_context()
    crypt_key = ctx.opts["crypt_key"]

    # 0. payment_gateway_type — bring to final state
    for value in [
        "CRYPTOPAY",
        "ROBOKASSA",
        "FREEKASSA",
        "MULENPAY",
        "PAYMASTER",
        "PLATEGA",
        "WATA",
        "HELEKET",
        "WATAPAY",
        "TRIBUTE",
        "KASSAI",
    ]:
        op.execute(f"ALTER TYPE payment_gateway_type ADD VALUE IF NOT EXISTS '{value}'")

    op.execute("ALTER TABLE payment_gateways ALTER COLUMN type TYPE text USING type::text")
    op.execute(
        "ALTER TABLE transactions ALTER COLUMN gateway_type TYPE text USING gateway_type::text"
    )

    for table, column in [("payment_gateways", "type"), ("transactions", "gateway_type")]:
        op.execute(f"""
            UPDATE {table}
            SET {column} = 'CRYPTOPAY'
            WHERE {column} IN ('WATAPAY', 'TRIBUTE', 'KASSAI')
        """)

    op.execute("""
        CREATE TYPE payment_gateway_type_new AS ENUM (
            'TELEGRAM_STARS',
            'YOOKASSA',
            'YOOMONEY',
            'CRYPTOMUS',
            'HELEKET',
            'CRYPTOPAY',
            'FREEKASSA',
            'MULENPAY',
            'PAYMASTER',
            'PLATEGA',
            'ROBOKASSA',
            'URLPAY',
            'WATA'
        )
    """)
    op.execute("""
        ALTER TABLE payment_gateways
        ALTER COLUMN type TYPE payment_gateway_type_new
        USING type::text::payment_gateway_type_new
    """)
    op.execute("""
        ALTER TABLE transactions
        ALTER COLUMN gateway_type TYPE payment_gateway_type_new
        USING gateway_type::text::payment_gateway_type_new
    """)
    op.execute("DROP TYPE payment_gateway_type")
    op.execute("ALTER TYPE payment_gateway_type_new RENAME TO payment_gateway_type")

    # 1. user_role — add new values
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'PREVIEW'")
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'OWNER'")
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'SYSTEM'")

    # 2. plans.is_trial — add BEFORE changing the enum
    op.add_column(
        "plans",
        sa.Column("is_trial", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute("UPDATE plans SET is_trial = TRUE WHERE availability = 'TRIAL'")

    # 3. plan_availability — recreate without TRIAL, add LINK
    op.execute("""
        CREATE TYPE plan_availability_new AS ENUM (
            'ALL', 'NEW', 'EXISTING', 'INVITED', 'ALLOWED', 'LINK'
        )
    """)
    op.execute("ALTER TABLE plans ALTER COLUMN availability TYPE text USING availability::text")
    op.execute("UPDATE plans SET availability = 'ALL' WHERE availability = 'TRIAL'")
    op.execute("""
        ALTER TABLE plans
        ALTER COLUMN availability TYPE plan_availability_new
        USING availability::text::plan_availability_new
    """)
    op.execute("DROP TYPE plan_availability")
    op.execute("ALTER TYPE plan_availability_new RENAME TO plan_availability")

    # 4. purchase_type enum — rename purchasetype → purchase_type
    op.execute("ALTER TYPE purchasetype RENAME TO purchase_type")

    # 5. users — add indexes, restrict string lengths
    op.execute("ALTER TABLE users ALTER COLUMN username TYPE VARCHAR(32)")
    op.execute("ALTER TABLE users ALTER COLUMN referral_code TYPE VARCHAR(64)")
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)
    op.create_index("ix_users_role", "users", ["role"], unique=False)
    op.create_index("ix_users_username", "users", ["username"], unique=False)
    op.create_index("ix_users_referral_code", "users", ["referral_code"], unique=True)

    op.add_column(
        "users",
        sa.Column(
            "is_trial_available",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.execute("""
        UPDATE users
        SET is_trial_available = FALSE
        WHERE telegram_id IN (
            SELECT DISTINCT user_telegram_id
            FROM subscriptions
            WHERE is_trial = TRUE
        )
    """)
    op.alter_column("users", "is_trial_available", server_default=None)

    # 5.1. plans/subscriptions — limits: -1 (unlimited) → 0
    op.execute("UPDATE plans SET traffic_limit = 0 WHERE traffic_limit = -1")
    op.execute("UPDATE plans SET device_limit = 0 WHERE device_limit = -1")
    op.execute("UPDATE subscriptions SET traffic_limit = 0 WHERE traffic_limit = -1")
    op.execute("UPDATE subscriptions SET device_limit = 0 WHERE device_limit = -1")
    op.execute("UPDATE plan_durations SET days = 0 WHERE days = -1")

    # 6. subscriptions — plan → plan_snapshot, add indexes
    op.alter_column("subscriptions", "plan", new_column_name="plan_snapshot")
    op.execute(
        "ALTER TABLE subscriptions ALTER COLUMN plan_snapshot TYPE JSONB USING plan_snapshot::jsonb"
    )
    op.create_index("ix_subscriptions_status", "subscriptions", ["status"], unique=False)
    op.create_index("ix_subscriptions_expire_at", "subscriptions", ["expire_at"], unique=False)
    op.create_index(
        "ix_subscriptions_user_remna_id", "subscriptions", ["user_remna_id"], unique=False
    )

    # 7. transactions — plan → plan_snapshot, pricing → JSONB, add indexes
    op.alter_column("transactions", "plan", new_column_name="plan_snapshot")
    op.execute(
        "ALTER TABLE transactions ALTER COLUMN plan_snapshot TYPE JSONB USING plan_snapshot::jsonb"
    )
    op.execute("ALTER TABLE transactions ALTER COLUMN pricing TYPE JSONB USING pricing::jsonb")
    op.create_index("ix_transactions_payment_id", "transactions", ["payment_id"], unique=True)
    op.create_index("ix_transactions_status", "transactions", ["status"], unique=False)
    op.create_index(
        "ix_transactions_user_telegram_id", "transactions", ["user_telegram_id"], unique=False
    )

    # 7.1. plan_snapshot — migrate to new structure
    op.execute("""
        UPDATE subscriptions
        SET plan_snapshot = plan_snapshot
            || jsonb_build_object(
                'is_trial', is_trial,
                'traffic_limit', CASE
                    WHEN (plan_snapshot->>'traffic_limit')::int = -1 THEN 0
                    ELSE (plan_snapshot->>'traffic_limit')::int
                END,
                'device_limit', CASE
                    WHEN (plan_snapshot->>'device_limit')::int = -1 THEN 0
                    ELSE (plan_snapshot->>'device_limit')::int
                END
            )
        WHERE plan_snapshot IS NOT NULL
    """)

    op.execute("""
        UPDATE transactions
        SET plan_snapshot = plan_snapshot
            || jsonb_build_object(
                'is_trial', false,
                'traffic_limit', CASE
                    WHEN (plan_snapshot->>'traffic_limit')::int = -1 THEN 0
                    ELSE (plan_snapshot->>'traffic_limit')::int
                END,
                'device_limit', CASE
                    WHEN (plan_snapshot->>'device_limit')::int = -1 THEN 0
                    ELSE (plan_snapshot->>'device_limit')::int
                END
            )
        WHERE plan_snapshot IS NOT NULL
    """)

    # 8. plan_durations — add order_index
    op.add_column(
        "plan_durations",
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("plan_durations", "order_index", server_default=None)
    op.create_index(
        "ix_plan_durations_order_index", "plan_durations", ["order_index"], unique=False
    )

    # 9. plans — add public_code, indexes
    op.add_column(
        "plans",
        sa.Column("public_code", sa.String(), nullable=False, server_default=""),
    )
    plans = conn.execute(sa.text("SELECT id FROM plans")).fetchall()
    for (plan_id,) in plans:
        code = _generate_public_code(plan_id, crypt_key)
        conn.execute(
            sa.text("UPDATE plans SET public_code = :code WHERE id = :id"),
            {"code": code, "id": plan_id},
        )
    op.alter_column("plans", "public_code", server_default=None)
    op.alter_column("plans", "is_trial", server_default=None)
    op.create_index("ix_plans_name", "plans", ["name"], unique=True)
    op.create_index("ix_plans_public_code", "plans", ["public_code"], unique=True)
    op.create_index("ix_plans_order_index", "plans", ["order_index"], unique=False)

    # 10. broadcasts — payload → JSONB, add index
    op.execute("ALTER TABLE broadcasts ALTER COLUMN payload TYPE JSONB USING payload::jsonb")
    op.create_index("ix_broadcasts_status", "broadcasts", ["status"], unique=False)

    # 11. broadcast_messages — user_id → user_telegram_id, add indexes
    op.alter_column("broadcast_messages", "user_id", new_column_name="user_telegram_id")
    op.create_index(
        "ix_broadcast_messages_broadcast_id", "broadcast_messages", ["broadcast_id"], unique=False
    )
    op.create_index("ix_broadcast_messages_status", "broadcast_messages", ["status"], unique=False)
    op.create_index(
        "ix_broadcast_messages_user_telegram_id",
        "broadcast_messages",
        ["user_telegram_id"],
        unique=False,
    )

    # 12. payment_gateways — settings → JSONB, add index
    op.create_index(
        "ix_payment_gateways_order_index", "payment_gateways", ["order_index"], unique=False
    )
    op.execute(
        "ALTER TABLE payment_gateways ALTER COLUMN settings TYPE JSONB USING settings::jsonb"
    )

    # 13. settings — full rework
    op.execute("ALTER TABLE settings ALTER COLUMN referral TYPE JSONB USING referral::jsonb")

    op.execute("""
        UPDATE settings
        SET referral = jsonb_set(
            referral,
            '{reward,config}',
            (referral->'reward'->'config') - '2'
        )
        WHERE (referral->>'level')::int = 1
        AND referral->'reward'->'config' ? '2'
    """)

    op.add_column("settings", sa.Column("access", postgresql.JSONB(), nullable=True))
    op.add_column("settings", sa.Column("requirements", postgresql.JSONB(), nullable=True))
    op.add_column("settings", sa.Column("notifications", postgresql.JSONB(), nullable=True))
    op.add_column("settings", sa.Column("menu", postgresql.JSONB(), nullable=True))
    op.add_column(
        "settings",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('UTC', now())"),
        ),
    )
    op.add_column(
        "settings",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('UTC', now())"),
        ),
    )

    op.execute("""
        UPDATE settings SET
            access = json_build_object(
                'mode', access_mode::text,
                'purchases_allowed', COALESCE(purchases_allowed, true),
                'registration_allowed', COALESCE(registration_allowed, true)
            )::jsonb,
            requirements = json_build_object(
                'rules_required', COALESCE(rules_required, false),
                'channel_required', COALESCE(channel_required, false),
                'rules_link', COALESCE(rules_link, 'https://telegram.org/tos/'),
                'channel_link', COALESCE(channel_link, '@remna_shop'),
                'channel_id', channel_id
            )::jsonb,
            notifications = json_build_object(
                'user', COALESCE(user_notifications, '{}'),
                'system', COALESCE(system_notifications, '{}')
            )::jsonb,
            menu = '{}'::jsonb
    """)

    op.alter_column("settings", "access", nullable=False)
    op.alter_column("settings", "requirements", nullable=False)
    op.alter_column("settings", "notifications", nullable=False)
    op.alter_column("settings", "menu", nullable=False)

    op.drop_column("settings", "rules_required")
    op.drop_column("settings", "channel_required")
    op.drop_column("settings", "rules_link")
    op.drop_column("settings", "channel_link")
    op.drop_column("settings", "access_mode")
    op.drop_column("settings", "purchases_allowed")
    op.drop_column("settings", "registration_allowed")
    op.drop_column("settings", "channel_id")
    op.drop_column("settings", "user_notifications")
    op.drop_column("settings", "system_notifications")
    op.execute("DROP TYPE IF EXISTS access_mode")

    # 14. referrals — indexes
    op.create_index(
        "ix_referrals_referred_telegram_id", "referrals", ["referred_telegram_id"], unique=True
    )
    op.create_index(
        "ix_referrals_referrer_telegram_id", "referrals", ["referrer_telegram_id"], unique=False
    )

    # 15. referral_rewards — index
    op.create_index(
        "ix_referral_rewards_user_telegram_id",
        "referral_rewards",
        ["user_telegram_id"],
        unique=False,
    )

    # 16. Truncate broadcast-related tables
    op.execute("TRUNCATE TABLE broadcast_messages CASCADE")
    op.execute("TRUNCATE TABLE broadcasts CASCADE")

    # 17. (from 0019) Drop promocode_activations and promocodes (FK dependency order matters)
    op.drop_table("promocode_activations")
    op.drop_table("promocodes")

    # 18. (from 0019) broadcast_messages — recreate FK with CASCADE
    op.drop_constraint(
        op.f("broadcast_messages_broadcast_id_fkey"), "broadcast_messages", type_="foreignkey"
    )
    op.create_foreign_key(
        op.f("broadcast_messages_broadcast_id_fkey"),
        "broadcast_messages",
        "broadcasts",
        ["broadcast_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 19. (from 0019) plans.allowed_user_ids — make NOT NULL
    op.execute("UPDATE plans SET allowed_user_ids = '{}' WHERE allowed_user_ids IS NULL")
    op.alter_column(
        "plans",
        "allowed_user_ids",
        existing_type=postgresql.ARRAY(sa.BIGINT()),
        nullable=False,
        server_default="{}",
    )

    # 19.1. subscriptions.traffic_limit_strategy — migrate to plan_traffic_limit_strategy type
    # Rename only if the old type still exists and the new one does not
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'traffic_limit_strategy')
            AND NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'plan_traffic_limit_strategy')
            THEN ALTER TYPE traffic_limit_strategy RENAME TO plan_traffic_limit_strategy;
            END IF;
        END$$;
    """)
    op.execute("""
        ALTER TABLE subscriptions
        ALTER COLUMN traffic_limit_strategy TYPE plan_traffic_limit_strategy
        USING traffic_limit_strategy::text::plan_traffic_limit_strategy
    """)

    # 20. (from 0019) Drop unique constraints (replaced by indexes from steps 5/7/9)
    op.drop_constraint(op.f("plans_name_key"), "plans", type_="unique")
    op.drop_constraint(op.f("transactions_payment_id_key"), "transactions", type_="unique")
    op.drop_constraint(op.f("uq_users_referral_code"), "users", type_="unique")
    # Use CASCADE — it will drop dependent FKs, which we then recreate explicitly
    op.execute("ALTER TABLE users DROP CONSTRAINT users_telegram_id_key CASCADE")
    op.create_foreign_key(
        op.f("referral_rewards_user_telegram_id_fkey"),
        "referral_rewards",
        "users",
        ["user_telegram_id"],
        ["telegram_id"],
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
    op.create_foreign_key(
        op.f("subscriptions_user_telegram_id_fkey"),
        "subscriptions",
        "users",
        ["user_telegram_id"],
        ["telegram_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        op.f("transactions_user_telegram_id_fkey"),
        "transactions",
        "users",
        ["user_telegram_id"],
        ["telegram_id"],
    )


def downgrade() -> None:
    # 20. Drop recreated FKs before restoring the constraint
    op.drop_constraint(
        op.f("referral_rewards_user_telegram_id_fkey"), "referral_rewards", type_="foreignkey"
    )
    op.drop_constraint(op.f("referrals_referrer_telegram_id_fkey"), "referrals", type_="foreignkey")
    op.drop_constraint(op.f("referrals_referred_telegram_id_fkey"), "referrals", type_="foreignkey")
    op.drop_constraint(
        op.f("subscriptions_user_telegram_id_fkey"), "subscriptions", type_="foreignkey"
    )
    op.drop_constraint(
        op.f("transactions_user_telegram_id_fkey"), "transactions", type_="foreignkey"
    )
    # Restore unique constraints
    op.create_unique_constraint(
        op.f("users_telegram_id_key"), "users", ["telegram_id"], postgresql_nulls_not_distinct=False
    )
    op.create_unique_constraint(
        op.f("uq_users_referral_code"),
        "users",
        ["referral_code"],
        postgresql_nulls_not_distinct=False,
    )
    op.create_unique_constraint(
        op.f("transactions_payment_id_key"),
        "transactions",
        ["payment_id"],
        postgresql_nulls_not_distinct=False,
    )
    op.create_unique_constraint(
        op.f("plans_name_key"), "plans", ["name"], postgresql_nulls_not_distinct=False
    )

    # 19. plans.allowed_user_ids — restore nullable
    op.alter_column(
        "plans",
        "allowed_user_ids",
        existing_type=postgresql.ARRAY(sa.BIGINT()),
        nullable=True,
        server_default=None,
    )

    # 19.1. subscriptions.traffic_limit_strategy — restore original enum name
    op.execute(
        """ALTER TABLE subscriptions ALTER COLUMN traffic_limit_strategy TYPE text
        USING traffic_limit_strategy::text"""
    )
    op.execute("ALTER TYPE plan_traffic_limit_strategy RENAME TO traffic_limit_strategy")
    op.execute("""
        ALTER TABLE subscriptions
        ALTER COLUMN traffic_limit_strategy TYPE traffic_limit_strategy
        USING traffic_limit_strategy::text::traffic_limit_strategy
    """)

    # 18. broadcast_messages — restore FK without CASCADE
    op.drop_constraint(
        op.f("broadcast_messages_broadcast_id_fkey"), "broadcast_messages", type_="foreignkey"
    )
    op.create_foreign_key(
        op.f("broadcast_messages_broadcast_id_fkey"),
        "broadcast_messages",
        "broadcasts",
        ["broadcast_id"],
        ["id"],
    )

    # 17. Restore promocodes and promocode_activations
    op.create_table(
        "promocode_activations",
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("promocode_id", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("user_telegram_id", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column(
            "activated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("timezone('UTC'::text, now())"),
            autoincrement=False,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["promocode_id"],
            ["promocodes.id"],
            name=op.f("promocode_activations_promocode_id_fkey"),
        ),
        sa.ForeignKeyConstraint(
            ["user_telegram_id"],
            ["users.telegram_id"],
            name=op.f("promocode_activations_user_telegram_id_fkey"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("promocode_activations_pkey")),
    )
    op.create_table(
        "promocodes",
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("code", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("is_active", sa.BOOLEAN(), autoincrement=False, nullable=False),
        sa.Column(
            "reward_type",
            postgresql.ENUM(
                "DURATION",
                "TRAFFIC",
                "SUBSCRIPTION",
                "PERSONAL_DISCOUNT",
                "PURCHASE_DISCOUNT",
                name="promocode_reward_type",
            ),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("reward", sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column(
            "plan", postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=True
        ),
        sa.Column("lifetime", sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column("max_activations", sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("timezone('UTC'::text, now())"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("timezone('UTC'::text, now())"),
            autoincrement=False,
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("promocodes_pkey")),
        sa.UniqueConstraint(
            "code",
            name=op.f("promocodes_code_key"),
            postgresql_include=[],
            postgresql_nulls_not_distinct=False,
        ),
    )

    # referral_rewards index
    op.drop_index("ix_referral_rewards_user_telegram_id", table_name="referral_rewards")

    # referrals indexes
    op.drop_index("ix_referrals_referrer_telegram_id", table_name="referrals")
    op.drop_index("ix_referrals_referred_telegram_id", table_name="referrals")

    # settings — restore old columns
    op.execute("CREATE TYPE access_mode AS ENUM ('PUBLIC', 'INVITED', 'RESTRICTED')")
    op.add_column(
        "settings",
        sa.Column("access_mode", sa.Enum(name="access_mode", create_type=False), nullable=True),
    )
    op.add_column("settings", sa.Column("rules_required", sa.Boolean(), nullable=True))
    op.add_column("settings", sa.Column("channel_required", sa.Boolean(), nullable=True))
    op.add_column("settings", sa.Column("rules_link", sa.String(), nullable=True))
    op.add_column("settings", sa.Column("channel_link", sa.String(), nullable=True))
    op.add_column("settings", sa.Column("channel_id", sa.BigInteger(), nullable=True))
    op.add_column("settings", sa.Column("purchases_allowed", sa.Boolean(), nullable=True))
    op.add_column("settings", sa.Column("registration_allowed", sa.Boolean(), nullable=True))
    op.add_column("settings", sa.Column("user_notifications", sa.JSON(), nullable=True))
    op.add_column("settings", sa.Column("system_notifications", sa.JSON(), nullable=True))
    op.execute("""
        UPDATE settings SET
            access_mode = (access->>'mode')::access_mode,
            purchases_allowed = (access->>'purchases_allowed')::boolean,
            registration_allowed = (access->>'registration_allowed')::boolean,
            rules_required = (requirements->>'rules_required')::boolean,
            channel_required = (requirements->>'channel_required')::boolean,
            rules_link = requirements->>'rules_link',
            channel_link = requirements->>'channel_link',
            channel_id = (requirements->>'channel_id')::bigint,
            user_notifications = (notifications->'user')::json,
            system_notifications = (notifications->'system')::json
    """)
    op.drop_column("settings", "created_at")
    op.drop_column("settings", "updated_at")
    op.drop_column("settings", "access")
    op.drop_column("settings", "requirements")
    op.drop_column("settings", "notifications")
    op.drop_column("settings", "menu")

    # broadcast_messages
    op.drop_index("ix_broadcast_messages_user_telegram_id", table_name="broadcast_messages")
    op.drop_index("ix_broadcast_messages_status", table_name="broadcast_messages")
    op.drop_index("ix_broadcast_messages_broadcast_id", table_name="broadcast_messages")
    op.alter_column("broadcast_messages", "user_telegram_id", new_column_name="user_id")

    # broadcasts
    op.drop_index("ix_broadcasts_status", table_name="broadcasts")

    # payment_gateways
    op.drop_index("ix_payment_gateways_order_index", table_name="payment_gateways")

    # plan_durations
    op.drop_index("ix_plan_durations_order_index", table_name="plan_durations")
    op.drop_column("plan_durations", "order_index")

    # plans
    op.drop_index("ix_plans_public_code", table_name="plans")
    op.drop_index("ix_plans_name", table_name="plans")
    op.drop_index("ix_plans_order_index", table_name="plans")
    op.drop_column("plans", "public_code")
    op.drop_column("plans", "is_trial")

    # plan_availability — restore TRIAL
    op.execute("""
        CREATE TYPE plan_availability_old AS ENUM (
            'ALL', 'NEW', 'EXISTING', 'INVITED', 'ALLOWED', 'TRIAL'
        )
    """)
    op.execute("ALTER TABLE plans ALTER COLUMN availability TYPE text USING availability::text")
    op.execute("""
        ALTER TABLE plans
        ALTER COLUMN availability TYPE plan_availability_old
        USING availability::text::plan_availability_old
    """)
    op.execute("DROP TYPE plan_availability")
    op.execute("ALTER TYPE plan_availability_old RENAME TO plan_availability")

    # transactions
    op.drop_index("ix_transactions_user_telegram_id", table_name="transactions")
    op.drop_index("ix_transactions_status", table_name="transactions")
    op.drop_index("ix_transactions_payment_id", table_name="transactions")
    op.alter_column("transactions", "plan_snapshot", new_column_name="plan")

    # subscriptions
    op.drop_index("ix_subscriptions_user_remna_id", table_name="subscriptions")
    op.drop_index("ix_subscriptions_expire_at", table_name="subscriptions")
    op.drop_index("ix_subscriptions_status", table_name="subscriptions")
    op.alter_column("subscriptions", "plan_snapshot", new_column_name="plan")

    # users
    op.drop_column("users", "is_trial_available")
    op.drop_index("ix_users_referral_code", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_index("ix_users_telegram_id", table_name="users")

    # 0 (unlimited) → -1
    op.execute("UPDATE plans SET traffic_limit = -1 WHERE traffic_limit = 0")
    op.execute("UPDATE plans SET device_limit = -1 WHERE device_limit = 0")
    op.execute("UPDATE subscriptions SET traffic_limit = -1 WHERE traffic_limit = 0")
    op.execute("UPDATE subscriptions SET device_limit = -1 WHERE device_limit = 0")
    op.execute("UPDATE plan_durations SET days = -1 WHERE days = 0")

    # purchase_type → purchasetype
    op.execute("ALTER TYPE purchase_type RENAME TO purchasetype")
