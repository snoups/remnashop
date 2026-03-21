from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    traffic_limit_strategy_enum = sa.Enum(
        "NO_RESET",
        "DAY",
        "WEEK",
        "MONTH",
        name="plan_traffic_limit_strategy",
    )
    traffic_limit_strategy_enum.create(op.get_bind(), checkfirst=True)

    op.add_column("plans", sa.Column("description", sa.String(), nullable=True))
    op.add_column("plans", sa.Column("tag", sa.String(), nullable=True))
    op.add_column(
        "plans",
        sa.Column(
            "traffic_limit_strategy",
            traffic_limit_strategy_enum,
            nullable=False,
            server_default="NO_RESET",
        ),
    )
    op.add_column("plans", sa.Column("external_squad", sa.ARRAY(sa.UUID()), nullable=True))


def downgrade() -> None:
    op.drop_column("plans", "external_squad")
    op.drop_column("plans", "traffic_limit_strategy")
    op.drop_column("plans", "tag")
    op.drop_column("plans", "description")
