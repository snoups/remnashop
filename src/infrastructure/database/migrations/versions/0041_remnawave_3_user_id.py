"""Remnawave 3.0: identify panel users by numeric id instead of uuid.

Remnawave 3.0 dropped the user UUID and keys users by an integer id. The mapping
from the old UUID to the new id is only known to the panel, so this migration
keeps the old value in ``legacy_remna_uuid`` (so the migration can be rolled back)
and resets ``user_remna_id`` to ``0`` ("not linked yet"). On startup the bot relinks
current subscriptions to panel users (see ``RelinkRemnaUsers``).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0041"
down_revision: Union[str, None] = "0040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_subscriptions_user_remna_id", table_name="subscriptions", if_exists=True)
    op.alter_column("subscriptions", "user_remna_id", new_column_name="legacy_remna_uuid")
    op.alter_column(
        "subscriptions",
        "legacy_remna_uuid",
        existing_type=postgresql.UUID(),
        nullable=True,
    )
    op.add_column(
        "subscriptions",
        sa.Column("user_remna_id", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_subscriptions_user_remna_id", "subscriptions", ["user_remna_id"])


def downgrade() -> None:
    op.drop_index("ix_subscriptions_user_remna_id", table_name="subscriptions")
    op.drop_column("subscriptions", "user_remna_id")
    # Rows created after the upgrade have no 2.x UUID; give them a placeholder so the
    # column can become NOT NULL again (such subscriptions will not match a 2.x panel user)
    op.execute(
        "UPDATE subscriptions SET legacy_remna_uuid = gen_random_uuid() "
        "WHERE legacy_remna_uuid IS NULL"
    )
    op.alter_column(
        "subscriptions",
        "legacy_remna_uuid",
        existing_type=postgresql.UUID(),
        nullable=False,
    )
    op.alter_column("subscriptions", "legacy_remna_uuid", new_column_name="user_remna_id")
    op.create_index("ix_subscriptions_user_remna_id", "subscriptions", ["user_remna_id"])
