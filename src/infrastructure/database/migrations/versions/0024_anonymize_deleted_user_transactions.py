from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "transactions_user_telegram_id_fkey",
        "transactions",
        type_="foreignkey",
    )
    op.alter_column(
        "transactions",
        "user_telegram_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )
    op.create_foreign_key(
        "transactions_user_telegram_id_fkey",
        "transactions",
        "users",
        ["user_telegram_id"],
        ["telegram_id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    if (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT 1 FROM transactions "
                "WHERE user_telegram_id IS NULL LIMIT 1"
            )
        )
        .first()
    ):
        raise RuntimeError(
            "Cannot downgrade while anonymized transactions with NULL user_telegram_id exist"
        )

    op.drop_constraint(
        "transactions_user_telegram_id_fkey",
        "transactions",
        type_="foreignkey",
    )
    op.alter_column(
        "transactions",
        "user_telegram_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.create_foreign_key(
        "transactions_user_telegram_id_fkey",
        "transactions",
        "users",
        ["user_telegram_id"],
        ["telegram_id"],
    )
