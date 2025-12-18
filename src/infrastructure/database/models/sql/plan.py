from decimal import Decimal
from typing import Optional
from uuid import UUID

from remnapy.enums.users import TrafficLimitStrategy
from sqlalchemy import ARRAY, BigInteger, Boolean, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.enums import Currency, PlanAvailability, PlanType

from .base import BaseSql
from .timestamp import TimestampMixin


class Plan(BaseSql, TimestampMixin):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    type: Mapped[PlanType] = mapped_column(
        Enum(
            PlanType,
            name="plan_type",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    availability: Mapped[PlanAvailability] = mapped_column(
        Enum(
            PlanAvailability,
            name="plan_availability",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tag: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    traffic_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    device_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    traffic_limit_strategy: Mapped[TrafficLimitStrategy] = mapped_column(
        Enum(
            TrafficLimitStrategy,
            name="plan_traffic_limit_strategy",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    allowed_user_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), nullable=True)
    internal_squads: Mapped[list[UUID]] = mapped_column(ARRAY(PG_UUID), nullable=False)
    external_squad: Mapped[Optional[UUID]] = mapped_column(ARRAY(PG_UUID), nullable=True)

    durations: Mapped[list["PlanDuration"]] = relationship(
        "PlanDuration",
        back_populates="plan",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PlanDuration(BaseSql):
    __tablename__ = "plan_durations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), nullable=False)

    days: Mapped[int] = mapped_column(Integer, nullable=False)

    prices: Mapped[list["PlanPrice"]] = relationship(
        "PlanPrice",
        back_populates="plan_duration",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    plan: Mapped["Plan"] = relationship("Plan", back_populates="durations")


class PlanPrice(BaseSql):
    __tablename__ = "plan_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    plan_duration_id: Mapped[int] = mapped_column(
        ForeignKey("plan_durations.id", ondelete="CASCADE"),
        nullable=False,
    )

    currency: Mapped[Currency] = mapped_column(
        Enum(
            Currency,
            name="currency",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    plan_duration: Mapped["PlanDuration"] = relationship("PlanDuration", back_populates="prices")
