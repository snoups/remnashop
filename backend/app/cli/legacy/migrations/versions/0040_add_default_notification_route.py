from typing import Sequence, Union

from alembic import op

revision: str = "0040"
down_revision: Union[str, None] = "0039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        UPDATE settings
        SET notifications = notifications
            || '{"default_route": {"chat_id": null, "thread_id": null}}'::jsonb
        WHERE NOT (notifications ? 'default_route')
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE settings
        SET notifications = notifications - 'default_route'
    """)
