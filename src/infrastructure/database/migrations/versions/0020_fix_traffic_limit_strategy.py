from typing import Sequence, Union

from alembic import op

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE plan_traffic_limit_strategy ADD VALUE IF NOT EXISTS 'MONTH_ROLLING'")


def downgrade() -> None:
    op.execute("""
        ALTER TABLE subscriptions
        ALTER COLUMN traffic_limit_strategy TYPE text
        USING traffic_limit_strategy::text
    """)

    op.execute("""
        CREATE TYPE plan_traffic_limit_strategy_new AS ENUM (
            SELECT enumlabel
            FROM pg_enum
            JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
            WHERE typname = 'plan_traffic_limit_strategy'
            AND enumlabel <> 'MONTH_ROLLING'
        )
    """)

    op.execute("DROP TYPE plan_traffic_limit_strategy")
    op.execute("ALTER TYPE plan_traffic_limit_strategy_new RENAME TO plan_traffic_limit_strategy")

    op.execute("""
        ALTER TABLE subscriptions
        ALTER COLUMN traffic_limit_strategy TYPE plan_traffic_limit_strategy
        USING traffic_limit_strategy::text::plan_traffic_limit_strategy
    """)
