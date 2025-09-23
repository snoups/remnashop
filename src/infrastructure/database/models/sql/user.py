from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .promocode import PromocodeActivation
    from .subscription import Subscription
    from .transaction import Transaction

from sqlalchemy import BigInteger, Boolean, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.enums import Locale, UserRole

from .base import BaseSql
from .timestamp import TimestampMixin


class User(BaseSql, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    language: Mapped[Locale] = mapped_column(Enum(Locale), nullable=False)

    personal_discount: Mapped[int] = mapped_column(Integer, nullable=False)
    purchase_discount: Mapped[int] = mapped_column(Integer, nullable=False)

    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_bot_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_trial_used: Mapped[bool] = mapped_column(Boolean, nullable=False)

    subscription: Mapped["Subscription"] = relationship(
        "Subscription",
        back_populates="user",
        foreign_keys="Subscription.user_telegram_id",
        cascade="all, delete-orphan",
        lazy="joined",
    )
    promocode_activations: Mapped[list["PromocodeActivation"]] = relationship(
        "PromocodeActivation",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="joined",
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="joined",
    )
