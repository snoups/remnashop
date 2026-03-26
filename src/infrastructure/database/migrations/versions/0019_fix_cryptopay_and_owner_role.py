from typing import Sequence, Union

from alembic import context, op

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        UPDATE payment_gateways
        SET settings = settings - 'secret_key'
        WHERE type = 'CRYPTOPAY'
        AND settings ? 'secret_key'
    """)

    ctx = context.get_context()
    owner_id = ctx.opts["owner_id"]

    if owner_id:
        op.execute(f"""
            UPDATE users
            SET role = 'OWNER'
            WHERE telegram_id = {int(owner_id)}
            AND role != 'OWNER'
        """)


def downgrade() -> None:
    pass
