from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "giveaway_campaigns",
        sa.Column("rules_text", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("giveaway_campaigns", "rules_text")
