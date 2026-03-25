"""Add system notification routes to settings.notifications JSONB

Revision ID: 0019
Revises: 0018
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'routes' key to existing notifications JSONB if not already present.
    # The column stores {"settings": {...}, "routes": {...}} after this migration.
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
