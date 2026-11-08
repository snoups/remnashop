from typing import Final, Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "1003"
down_revision: Union[str, None] = "1002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES: Final[tuple[str, ...]] = ("event_log_entries", "event_outbox")
# event type -> (old category, new category)
_MOVES: Final[dict[str, tuple[str, str]]] = {
    "AddOnChangedEvent": ("SUBSCRIPTION", "PLANS"),
    "BackupCompletedEvent": ("SETTINGS", "INFRASTRUCTURE"),
    "BackupFailedEvent": ("SETTINGS", "INFRASTRUCTURE"),
}


def _move(to_index: int) -> None:
    connection = op.get_bind()
    for table in _TABLES:
        for event_type, categories in _MOVES.items():
            connection.execute(
                sa.text(
                    f"UPDATE {table} SET category = CAST(:category AS event_category)"
                    " WHERE event_type = :event_type"
                ),
                {"category": categories[to_index], "event_type": event_type},
            )


def upgrade() -> None:
    _move(1)


def downgrade() -> None:
    _move(0)
