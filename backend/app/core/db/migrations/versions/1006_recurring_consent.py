from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision: str = "1006"
down_revision: Union[str, None] = "1005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fresh installations get the final schema from 1005. Preserve this revision
    # so databases stamped by the previously published consent migration upgrade.
    if context.is_offline_mode() or sa.inspect(op.get_bind()).has_table("recurring_consents"):
        return
    op.create_table(
        "recurring_consents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "subscription_id", sa.Integer(), sa.ForeignKey("subscriptions.id", ondelete="SET NULL")
        ),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("telegram_id", sa.BigInteger()),
        sa.Column("event_id", sa.String(128)),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("terms", postgresql.JSONB(), nullable=False),
        sa.Column(
            "accepted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_channel", sa.String(16)),
        sa.Column("revoked_event_id", sa.String(128)),
        sa.Column("revoked_ip_address", sa.String(45)),
    )
    op.create_index("ix_recurring_consents_user_id", "recurring_consents", ["user_id"])
    op.create_index(
        "ix_recurring_consents_subscription_id", "recurring_consents", ["subscription_id"]
    )
    op.add_column("transactions", sa.Column("recurring_consent_id", sa.Integer()))
    op.create_foreign_key(
        "fk_transactions_recurring_consent_id_recurring_consents",
        "transactions",
        "recurring_consents",
        ["recurring_consent_id"],
        ["id"],
    )
    op.add_column("recurring_payments", sa.Column("consent_id", sa.Integer()))
    op.create_foreign_key(
        "fk_recurring_payments_consent_id_recurring_consents",
        "recurring_payments",
        "recurring_consents",
        ["consent_id"],
        ["id"],
    )
    op.alter_column("recurring_payments", "enabled", server_default=sa.text("false"))
    # Earlier versions enrolled by default and cannot prove explicit authorization.
    op.execute(
        "UPDATE recurring_payments SET enabled = false, disabled_at = now(), "
        "last_error = CASE WHEN last_error = 'payment_status_unknown' THEN last_error "
        "ELSE 'consent_required' END"
    )


def downgrade() -> None:
    # 1005 now owns the complete initial schema, including the consent tables.
    # Dropping them here would break both a fresh 1005 database and its rollback.
    pass
