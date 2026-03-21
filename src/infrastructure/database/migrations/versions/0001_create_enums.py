from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TYPE payment_gateway_type AS ENUM (
            'TELEGRAM_STARS',
            'YOOKASSA',
            'YOOMONEY',
            'CRYPTOMUS',
            'HELEKET',
            'URLPAY'
        )
    """)

    op.execute("""
        CREATE TYPE currency AS ENUM ('USD', 'XTR', 'RUB')
    """)

    op.execute("""
        CREATE TYPE plan_type AS ENUM (
            'TRAFFIC',
            'DEVICES',
            'BOTH',
            'UNLIMITED'
        )
    """)

    op.execute("""
        CREATE TYPE plan_availability AS ENUM (
            'ALL',
            'NEW',
            'EXISTING',
            'INVITED',
            'ALLOWED',
            'TRIAL'
        )
    """)

    op.execute("""
        CREATE TYPE promocode_reward_type AS ENUM (
            'DURATION',
            'TRAFFIC',
            'SUBSCRIPTION',
            'PERSONAL_DISCOUNT',
            'PURCHASE_DISCOUNT'
        )
    """)

    op.execute("""
        CREATE TYPE access_mode AS ENUM (
            'ALL',
            'INVITED',
            'PURCHASE',
            'BLOCKED'
        )
    """)

    op.execute("""
        CREATE TYPE subscription_status AS ENUM (
            'ACTIVE',
            'DISABLED',
            'LIMITED',
            'EXPIRED',
            'DELETED'
        )
    """)

    op.execute("""
        CREATE TYPE user_role AS ENUM ('DEV', 'ADMIN', 'USER')
    """)

    op.execute("""
        CREATE TYPE locale AS ENUM (
            'AR', 'AZ', 'BE', 'CS', 'DE', 'EN', 'ES', 'FA',
            'FR', 'HE', 'HI', 'ID', 'IT', 'JA', 'KK', 'KO',
            'MS', 'NL', 'PL', 'PT', 'RO', 'RU', 'SR', 'TR',
            'UK', 'UZ', 'VI'
        )
    """)

    op.execute("""
        CREATE TYPE transaction_status AS ENUM (
            'PENDING',
            'COMPLETED',
            'CANCELED',
            'REFUNDED',
            'FAILED'
        )
    """)

    op.execute("""
        CREATE TYPE purchasetype AS ENUM ('NEW', 'RENEW', 'CHANGE')
    """)


def downgrade() -> None:
    op.execute("DROP TYPE IF EXISTS purchasetype")
    op.execute("DROP TYPE IF EXISTS transaction_status")
    op.execute("DROP TYPE IF EXISTS locale")
    op.execute("DROP TYPE IF EXISTS user_role")
    op.execute("DROP TYPE IF EXISTS subscription_status")
    op.execute("DROP TYPE IF EXISTS access_mode")
    op.execute("DROP TYPE IF EXISTS promocode_reward_type")
    op.execute("DROP TYPE IF EXISTS plan_availability")
    op.execute("DROP TYPE IF EXISTS plan_type")
    op.execute("DROP TYPE IF EXISTS currency")
    op.execute("DROP TYPE IF EXISTS payment_gateway_type")
