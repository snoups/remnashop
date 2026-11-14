from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.encrypted_string import EncryptedString
from app.core.db.timestamp import TimestampMixin


class RecurringPayment(BaseSql, TimestampMixin):
    __tablename__ = "recurring_payments"

    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"), primary_key=True
    )
    source_transaction_id: Mapped[Optional[int]] = mapped_column(ForeignKey("transactions.id"))
    payment_method_id: Mapped[Optional[str]] = mapped_column(EncryptedString())
    shop_id: Mapped[str] = mapped_column(String(128), default="", server_default="")
    consent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("recurring_consents.id"))
    enabled: Mapped[bool] = mapped_column(default=False, server_default="false")
    customer_disabled: Mapped[bool] = mapped_column(default=False, server_default="false")
    disabled_at: Mapped[Optional[datetime]]
    # Codes, not provider error bodies, which can contain payment credentials.
    last_error: Mapped[Optional[str]] = mapped_column(String(64))
    pending_transaction_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("transactions.id"), unique=True
    )
    # Durable intent after authorization: a crash after it may have reached YooKassa.
    submitted_at: Mapped[Optional[datetime]]
    first_failure_at: Mapped[Optional[datetime]]
    retry_count: Mapped[int] = mapped_column(default=0, server_default="0")
    # The expiry this cycle pays for; a manual extension supersedes unsent retries.
    cycle_expire_at: Mapped[Optional[datetime]]
    pending_since: Mapped[Optional[datetime]]
    upcoming_notified_for: Mapped[Optional[datetime]]
    # Queue ownership must not change the business schedule or the bank retry deadline.
    leased_until: Mapped[Optional[datetime]]
    bank_retry_at: Mapped[Optional[datetime]]
    next_attempt_at: Mapped[datetime] = mapped_column(index=True)
