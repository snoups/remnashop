from typing import Sequence, Union

from alembic import op

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE promo_audience ADD VALUE IF NOT EXISTS 'WITHOUT_ACTIVE_SUBSCRIPTION'")


def downgrade() -> None:
    # Removing a value from a PostgreSQL enum requires recreating the type,
    # which is unsafe and out of scope for a simple rollback.
    pass
