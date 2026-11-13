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
    enabled: Mapped[bool] = mapped_column(default=True, server_default="true")
    customer_disabled: Mapped[bool] = mapped_column(default=False, server_default="false")
    disabled_at: Mapped[Optional[datetime]]
    # Codes, not provider error bodies, which can contain payment credentials.
    last_error: Mapped[Optional[str]] = mapped_column(String(64))
    pending_transaction_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("transactions.id"), unique=True
    )
    attempted_at: Mapped[Optional[datetime]]
    next_attempt_at: Mapped[datetime] = mapped_column(index=True)
