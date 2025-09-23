from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .user import User

from uuid import UUID

from sqlalchemy import DECIMAL as PG_DECIMAL
from sqlalchemy import JSON, BigInteger, Enum, ForeignKey, Integer
from sqlalchemy import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.enums import Currency, PaymentGatewayType, TransactionStatus

from .base import BaseSql
from .timestamp import TimestampMixin


class Transaction(BaseSql, TimestampMixin):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    payment_id: Mapped[UUID] = mapped_column(PG_UUID, nullable=False, unique=True)

    status: Mapped[TransactionStatus] = mapped_column(Enum(TransactionStatus), nullable=False)
    gateway: Mapped[PaymentGatewayType] = mapped_column(Enum(PaymentGatewayType), nullable=False)
    amount: Mapped[Decimal] = mapped_column(PG_DECIMAL, nullable=False)
    currency: Mapped[Currency] = mapped_column(Enum(Currency), nullable=False)
    plan: Mapped[dict] = mapped_column(JSON, nullable=False)

    user_telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id"),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="transactions", lazy="joined")
