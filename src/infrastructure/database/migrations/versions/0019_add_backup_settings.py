from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_BACKUP = '{"enabled": false, "interval_hours": 24, "max_files": 7, "send_to_chat": true}'


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column(
            "backup",
            postgresql.JSONB(),
            nullable=True,
        ),
    )
    op.execute(f"UPDATE settings SET backup = '{DEFAULT_BACKUP}'::jsonb WHERE backup IS NULL")
    op.alter_column("settings", "backup", nullable=False)


def downgrade() -> None:
    op.drop_column("settings", "backup")
