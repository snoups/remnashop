from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import Field

from src.core.enums import Currency, PlanAvailability, PlanType

from .base import TrackableDto


class PlanSnapshotDto(TrackableDto):
    id: int
    name: str
    type: PlanType
    traffic_limit: int
    device_limit: int
    duration: int
    squad_ids: list[UUID]

    @property
    def is_unlimited_duration(self) -> bool:
        return self.duration == -1

    @classmethod
    def from_plan(cls, plan: "PlanDto", duration_days: int) -> "PlanSnapshotDto":
        return cls(
            id=plan.id,
            name=plan.name,
            type=plan.type,
            traffic_limit=plan.traffic_limit,
            device_limit=plan.device_limit,
            duration=duration_days,
            squad_ids=plan.squad_ids.copy(),
        )

    @classmethod
    def test(cls) -> "PlanSnapshotDto":
        return cls(
            id=-1,
            name="test",
            type=PlanType.UNLIMITED,
            traffic_limit=-1,
            device_limit=-1,
            duration=-1,
            squad_ids=[],
        )


class PlanDto(TrackableDto):
    id: Optional[int] = Field(default=None, frozen=True)

    name: str = "Default Plan"
    type: PlanType = PlanType.BOTH
    is_active: bool = False

    traffic_limit: int = 100
    device_limit: int = 1

    # TODO: Add tag and traffic_reset_strategy

    availability: PlanAvailability = PlanAvailability.ALL
    allowed_user_ids: list[int] = []
    squad_ids: list[UUID] = []

    durations: list["PlanDurationDto"] = []

    @property
    def is_unlimited_traffic(self) -> bool:
        return self.type not in {PlanType.TRAFFIC, PlanType.BOTH}

    @property
    def is_unlimited_devices(self) -> bool:
        return self.type not in {PlanType.DEVICES, PlanType.BOTH}

    def get_duration(self, days: int) -> Optional["PlanDurationDto"]:
        return next((d for d in self.durations if d.days == days), None)


class PlanDurationDto(TrackableDto):
    id: Optional[int] = Field(default=None, frozen=True)

    days: int

    prices: list["PlanPriceDto"] = []

    @property
    def is_unlimited(self) -> bool:
        return self.days == -1

    def get_price(self, currency: Currency) -> Decimal:
        return next((p.price for p in self.prices if p.currency == currency))

    def get_price_per_day(self, currency: Currency) -> Optional[Decimal]:
        if self.days <= 0:
            return None

        for price in self.prices:
            if price.currency == currency:
                return price.price / Decimal(self.days)
        return None


class PlanPriceDto(TrackableDto):
    id: Optional[int] = Field(default=None, frozen=True)

    currency: Currency
    price: Decimal
