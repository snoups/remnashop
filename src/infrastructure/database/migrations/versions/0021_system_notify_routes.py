from typing import Sequence, Union

from alembic import op

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        UPDATE settings
        SET notifications = notifications || '{"routes": {}}'::jsonb
        WHERE NOT (notifications ? 'routes')
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE settings
        SET notifications = notifications - 'routes'
    """)
