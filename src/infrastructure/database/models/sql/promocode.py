from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .user import User

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.enums import PromocodeRewardType

from .base import BaseSql
from .timestamp import NOW_FUNC, TimestampMixin


class Promocode(BaseSql, TimestampMixin):
    __tablename__ = "promocodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    code: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    reward_type: Mapped[PromocodeRewardType] = mapped_column(
        Enum(PromocodeRewardType),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)

    reward: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # TODO: Implement storing plan for activation (relationship plan_duration?)

    lifetime: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_activations: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    activations: Mapped[list["PromocodeActivation"]] = relationship(
        "PromocodeActivation",
        back_populates="promocode",
        cascade="all, delete-orphan",
    )


class PromocodeActivation(BaseSql):
    __tablename__ = "promocode_activations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    promocode_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("promocodes.id"),
        nullable=False,
    )
    user_telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id"),
        nullable=False,
    )

    activated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=NOW_FUNC,
        nullable=False,
    )

    promocode: Mapped["Promocode"] = relationship("Promocode", back_populates="activations")
    user: Mapped["User"] = relationship("User", back_populates="promocode_activations")
