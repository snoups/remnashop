from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    entry_source = postgresql.ENUM(
        "AUTO_PURCHASE",
        "MANUAL",
        name="giveaway_entry_source",
        create_type=False,
    )
    entry_source.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "giveaway_entries",
        sa.Column(
            "entry_source",
            entry_source,
            server_default=sa.text("'AUTO_PURCHASE'::giveaway_entry_source"),
            nullable=False,
        ),
    )
    op.alter_column(
        "giveaway_entries",
        "user_telegram_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )
    op.alter_column(
        "giveaway_entries",
        "transaction_payment_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.alter_column(
        "giveaway_entries",
        "purchase_type",
        existing_type=postgresql.ENUM(
            "NEW",
            "RENEW",
            "CHANGE",
            name="purchase_type",
            create_type=False,
        ),
        nullable=True,
    )
    op.create_check_constraint(
        "ck_giveaway_entry_source_fields",
        "giveaway_entries",
        "("
        "entry_source = 'AUTO_PURCHASE' "
        "AND user_telegram_id IS NOT NULL "
        "AND transaction_payment_id IS NOT NULL "
        "AND purchase_type IS NOT NULL"
        ") OR ("
        "entry_source = 'MANUAL' "
        "AND user_telegram_id IS NULL "
        "AND transaction_payment_id IS NULL "
        "AND purchase_type IS NULL "
        "AND phone IS NOT NULL"
        ")",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_giveaway_entry_source_fields",
        "giveaway_entries",
        type_="check",
    )
    op.execute("DELETE FROM giveaway_entries WHERE entry_source = 'MANUAL'")
    op.alter_column(
        "giveaway_entries",
        "purchase_type",
        existing_type=postgresql.ENUM(
            "NEW",
            "RENEW",
            "CHANGE",
            name="purchase_type",
            create_type=False,
        ),
        nullable=False,
    )
    op.alter_column(
        "giveaway_entries",
        "transaction_payment_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.alter_column(
        "giveaway_entries",
        "user_telegram_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.drop_column("giveaway_entries", "entry_source")
    op.execute("DROP TYPE IF EXISTS giveaway_entry_source")
