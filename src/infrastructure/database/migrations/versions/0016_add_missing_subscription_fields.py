from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    traffic_limit_strategy_enum = sa.Enum(
        "NO_RESET",
        "DAY",
        "WEEK",
        "MONTH",
        name="traffic_limit_strategy",
    )
    traffic_limit_strategy_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "subscriptions",
        sa.Column(
            "traffic_limit_strategy",
            traffic_limit_strategy_enum,
            nullable=True,
        ),
    )
    op.add_column("subscriptions", sa.Column("tag", sa.String(), nullable=True))

    op.execute(
        """
        UPDATE subscriptions
        SET traffic_limit_strategy = CASE
            WHEN plan->>'traffic_limit_strategy' IN (
                'NO_RESET', 'DAY', 'WEEK', 'MONTH'
            )
            THEN (plan->>'traffic_limit_strategy')::traffic_limit_strategy
            ELSE 'NO_RESET'::traffic_limit_strategy
        END,
        tag = NULLIF(plan->>'tag', '')
        """
    )

    op.alter_column(
        "subscriptions",
        "traffic_limit_strategy",
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "tag")
    op.drop_column("subscriptions", "traffic_limit_strategy")
