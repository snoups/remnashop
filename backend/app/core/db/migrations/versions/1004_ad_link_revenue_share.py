from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "1004"
down_revision: Union[str, None] = "1003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ad_links",
        sa.Column(
            "revenue_share_percent",
            sa.Numeric(precision=5, scale=2),
            server_default="0",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_ad_links_revenue_share_percent_range"),
        "ad_links",
        "revenue_share_percent >= 0 AND revenue_share_percent <= 100",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_ad_links_revenue_share_percent_range"), "ad_links", type_="check")
    op.drop_column("ad_links", "revenue_share_percent")
