from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("COMMIT"))
    op.execute(sa.text("BEGIN"))

    # Remove secret_key from CRYPTOPAY gateway
    op.execute("""
        UPDATE payment_gateways
        SET settings = settings - 'secret_key'
        WHERE type = 'CRYPTOPAY'
        AND settings ? 'secret_key'
    """)

    # Fix menu button payloads: ensure URL/WEB_APP buttons have https:// links
    op.execute(
        sa.text("""
        UPDATE settings
        SET menu = (
            SELECT jsonb_set(
                menu,
                '{buttons}',
                (
                    SELECT jsonb_agg(
                        CASE
                            WHEN (btn->>'type') = ANY(ARRAY['URL', 'WEB_APP'])
                            AND (btn->>'payload') NOT LIKE 'https://%'
                            THEN jsonb_set(btn, '{payload}', to_jsonb('https://github.com/snoups/remnashop'::text))
                            ELSE btn
                        END
                    )
                    FROM jsonb_array_elements(menu->'buttons') AS btn
                )
            )
        )
        WHERE menu ? 'buttons'
        AND EXISTS (
            SELECT 1
            FROM jsonb_array_elements(menu->'buttons') AS btn
            WHERE (btn->>'type') = ANY(ARRAY['URL', 'WEB_APP'])
                AND (btn->>'payload') NOT LIKE 'https://%'
        )
    """)
    )

    # Set owner role
    ctx = context.get_context()
    owner_id = ctx.opts["owner_id"]

    if owner_id:
        op.execute(
            sa.text(
                "UPDATE users SET role = 'OWNER' WHERE telegram_id = :owner_id AND role != 'OWNER'"
            ).bindparams(owner_id=int(owner_id))
        )


def downgrade() -> None:
    pass
