from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op

revision: str = "1007"
down_revision: Union[str, None] = "1006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _upgrade_legacy_consent_owner() -> None:
    # Offline SQL targets a fresh chain: 1005 already creates the owner linkage.
    # Repairs of previously deployed schemas require the live database catalog.
    if not context.is_offline_mode():
        inspector = sa.inspect(op.get_bind())
        columns = {column["name"] for column in inspector.get_columns("recurring_consents")}
        if "owner_user_id" not in columns:
            op.add_column("recurring_consents", sa.Column("owner_user_id", sa.Integer()))
            op.create_foreign_key(
                "fk_recurring_consents_owner_user_id_users",
                "recurring_consents",
                "users",
                ["owner_user_id"],
                ["id"],
                ondelete="CASCADE",
            )
            op.create_index(
                "ix_recurring_consents_owner_user_id", "recurring_consents", ["owner_user_id"]
            )
        transaction_columns = {column["name"] for column in inspector.get_columns("transactions")}
        if "recurring_consent" in transaction_columns:
            op.drop_column("transactions", "recurring_consent")
    # An older binary can insert new authorizations after a rollback. A merge may
    # also have changed the resource owner while its original author stays intact.
    op.execute(
        "UPDATE recurring_consents AS consent SET owner_user_id = COALESCE("
        "(SELECT user_id FROM subscriptions WHERE id = consent.subscription_id), "
        "(SELECT user_id FROM transactions WHERE recurring_consent_id = consent.id "
        "ORDER BY id DESC LIMIT 1), consent.user_id) WHERE consent.owner_user_id IS NULL"
    )
    # The old binary can abandon an unlinked authorization before its author is
    # purged. Keep every payment reference; only a fully ownerless orphan is safe
    # to remove before restoring the current-owner invariant.
    op.execute(
        "DELETE FROM recurring_consents AS consent "
        "WHERE consent.owner_user_id IS NULL AND consent.user_id IS NULL "
        "AND consent.subscription_id IS NULL "
        "AND NOT EXISTS (SELECT 1 FROM transactions "
        "WHERE transactions.recurring_consent_id = consent.id) "
        "AND NOT EXISTS (SELECT 1 FROM recurring_payments "
        "WHERE recurring_payments.consent_id = consent.id)"
    )
    op.alter_column("recurring_consents", "owner_user_id", nullable=False)


def _retain_original_consent_author() -> None:
    # Fresh 1005 already retains the author snapshot; old 1006 cascades the whole
    # authorization when a merged source account is eventually purged.
    if context.is_offline_mode():
        return
    inspector = sa.inspect(op.get_bind())
    for constraint in inspector.get_foreign_keys("recurring_consents"):
        if constraint["constrained_columns"] == ["user_id"]:
            if constraint.get("options", {}).get("ondelete") == "SET NULL":
                break
            name = constraint["name"]
            if name is None:
                raise ValueError("Recurring consent author foreign key must be named")
            op.drop_constraint(name, "recurring_consents", type_="foreignkey")
            op.create_foreign_key(
                "fk_recurring_consents_user_id_users",
                "recurring_consents",
                "users",
                ["user_id"],
                ["id"],
                ondelete="SET NULL",
            )
            break
    op.alter_column("recurring_consents", "user_id", nullable=True)


def upgrade() -> None:
    _upgrade_legacy_consent_owner()
    _retain_original_consent_author()
    for name in (
        "first_failure_at",
        "cycle_expire_at",
        "pending_since",
        "upcoming_notified_for",
        "leased_until",
        "bank_retry_at",
    ):
        op.add_column("recurring_payments", sa.Column(name, sa.DateTime(timezone=True)))
    op.add_column(
        "recurring_payments",
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
    )
    # Existing in-flight attempts need their original age, not a fresh timeout
    # every time the worker sees a NULL value after deployment.
    op.execute(
        "UPDATE recurring_payments SET pending_since = transactions.created_at "
        "FROM transactions WHERE recurring_payments.pending_transaction_id = transactions.id"
    )


def downgrade() -> None:
    # The previously published 1006 application still reads this boolean. Restore
    # it from actual authorization records rather than invent consent for old orders.
    op.execute(
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS recurring_consent "
        "boolean NOT NULL DEFAULT false"
    )
    op.execute(
        "UPDATE transactions SET recurring_consent = true WHERE recurring_consent_id IS NOT NULL"
    )
    # The old application omits this newly introduced column on INSERT.
    op.alter_column("recurring_consents", "owner_user_id", nullable=True)
    op.drop_column("recurring_payments", "retry_count")
    for name in (
        "bank_retry_at",
        "leased_until",
        "upcoming_notified_for",
        "pending_since",
        "cycle_expire_at",
        "first_failure_at",
    ):
        op.drop_column("recurring_payments", name)
