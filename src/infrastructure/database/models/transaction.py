from typing import Any, Optional
from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.enums import Currency, PaymentGatewayType, PurchaseType, TransactionStatus

from .base import BaseSql
from .timestamp import TimestampMixin
from .user import User


class Transaction(BaseSql, TimestampMixin):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[UUID] = mapped_column(index=True, unique=True)
    user_telegram_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    status: Mapped[TransactionStatus] = mapped_column(index=True)
    is_test: Mapped[bool]

    purchase_type: Mapped[PurchaseType]
    gateway_type: Mapped[PaymentGatewayType]

    pricing: Mapped[dict[str, Any]]
    currency: Mapped[Currency]
    plan_snapshot: Mapped[dict[str, Any]]

    promocode_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("promocodes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    user: Mapped["User"] = relationship(foreign_keys=[user_telegram_id])
