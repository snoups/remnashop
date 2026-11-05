from typing import Sequence, Union

from alembic import op

revision: str = "0039"
down_revision: Union[str, None] = "0038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # settings may be a SQL NULL or a JSONB `null` depending on how the
    # gateway was originally persisted; backfill both representations.
    op.execute(
        """
        UPDATE payment_gateways
        SET settings = '{"display_name": null, "type": "TELEGRAM_STARS"}'::jsonb
        WHERE type = 'TELEGRAM_STARS'
          AND (settings IS NULL OR settings = 'null'::jsonb)
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE payment_gateways
        SET settings = NULL
        WHERE type = 'TELEGRAM_STARS'
          AND settings = '{"display_name": null, "type": "TELEGRAM_STARS"}'::jsonb
        """
    )
