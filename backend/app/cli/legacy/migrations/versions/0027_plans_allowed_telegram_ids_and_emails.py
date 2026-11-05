from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop entries whose telegram_id no longer has a matching user
    op.execute("""
        UPDATE plans
        SET allowed_user_ids = (
            SELECT COALESCE(
                array_agg(u.telegram_id ORDER BY u.telegram_id),
                '{}'::bigint[]
            )
            FROM unnest(allowed_user_ids) AS tg_id
            JOIN users u ON u.telegram_id = tg_id
            WHERE u.telegram_id IS NOT NULL
        )
        WHERE allowed_user_ids != '{}'
    """)
    op.alter_column("plans", "allowed_user_ids", new_column_name="allowed_telegram_ids")
    op.add_column(
        "plans",
        sa.Column(
            "allowed_emails",
            sa.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    op.drop_column("plans", "allowed_emails")
    op.alter_column("plans", "allowed_telegram_ids", new_column_name="allowed_user_ids")
