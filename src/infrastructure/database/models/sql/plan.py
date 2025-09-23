from decimal import Decimal
from uuid import UUID

from sqlalchemy import ARRAY, BigInteger, Boolean, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.enums import Currency, PlanAvailability, PlanType

from .base import BaseSql
from .timestamp import TimestampMixin


class Plan(BaseSql, TimestampMixin):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    type: Mapped[PlanType] = mapped_column(Enum(PlanType), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)

    traffic_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    device_limit: Mapped[int] = mapped_column(Integer, nullable=False)

    availability: Mapped[PlanAvailability] = mapped_column(Enum(PlanAvailability), nullable=False)
    allowed_user_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), nullable=True)
    squad_ids: Mapped[list[UUID]] = mapped_column(ARRAY(PG_UUID), nullable=False)

    durations: Mapped[list["PlanDuration"]] = relationship(
        "PlanDuration",
        back_populates="plan",
        cascade="all, delete-orphan",
        lazy="joined",
    )


class PlanDuration(BaseSql):
    __tablename__ = "plan_durations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    days: Mapped[int] = mapped_column(Integer, nullable=False)

    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), nullable=False)

    prices: Mapped[list["PlanPrice"]] = relationship(
        "PlanPrice",
        back_populates="plan_duration",
        cascade="all, delete-orphan",
        lazy="joined",
    )
    plan: Mapped["Plan"] = relationship("Plan", back_populates="durations")


class PlanPrice(BaseSql):
    __tablename__ = "plan_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    currency: Mapped[Currency] = mapped_column(Enum(Currency), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    plan_duration_id: Mapped[int] = mapped_column(
        ForeignKey("plan_durations.id", ondelete="CASCADE"),
        nullable=False,
    )

    plan_duration: Mapped["PlanDuration"] = relationship("PlanDuration", back_populates="prices")
