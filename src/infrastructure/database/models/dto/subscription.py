from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from src.core.utils.formatters import format_bytes_to_gb, format_device_count

if TYPE_CHECKING:
    from .plan import PlanDto, PlanSnapshotDto
    from .user import BaseUserDto

from datetime import datetime
from uuid import UUID

from loguru import logger
from pydantic import BaseModel, Field
from remnawave.enums import TrafficLimitStrategy

from src.core.enums import PlanType, SubscriptionStatus

from .base import TrackableDto


class RemnaSubscriptionDto(BaseModel):
    uuid: UUID
    status: SubscriptionStatus
    expire_at: datetime
    url: str

    traffic_limit: int
    device_limit: int
    traffic_limit_strategy: Optional[TrafficLimitStrategy] = None

    tag: Optional[str] = None
    internal_squads: list[UUID]
    external_squad: Optional[UUID] = None

    @classmethod
    def from_remna_user(cls, user: dict[str, Any]) -> "RemnaSubscriptionDto":
        def get_field(*keys: str, default: Any = None) -> Any:
            for key in keys:
                if key in user:
                    return user[key]
            return default

        traffic_limit_bytes = get_field("traffic_limit_bytes", "trafficLimitBytes")
        hwid_device_limit = get_field("hwid_device_limit", "hwidDeviceLimit")

        raw_squads = get_field("active_internal_squads", "activeInternalSquads", default=[])
        internal_squads = [
            s["uuid"] if isinstance(s, dict) and "uuid" in s else s for s in raw_squads
        ]

        return cls(
            uuid=get_field("uuid"),
            status=get_field("status"),
            expire_at=get_field("expire_at", "expireAt"),
            url=get_field("subscription_url", "subscriptionUrl", default=""),
            traffic_limit=format_bytes_to_gb(traffic_limit_bytes),
            device_limit=format_device_count(hwid_device_limit),
            traffic_limit_strategy=get_field("traffic_limit_strategy", "trafficLimitStrategy"),
            tag=get_field("tag", default=None),
            internal_squads=internal_squads,
            external_squad=get_field("external_squad_uuid", "externalSquadUuid", default=None),
        )


class BaseSubscriptionDto(TrackableDto):
    id: Optional[int] = Field(default=None, frozen=True)

    user_remna_id: UUID

    status: SubscriptionStatus = SubscriptionStatus.ACTIVE
    is_trial: bool = False

    traffic_limit: int
    device_limit: int
    internal_squads: list[UUID]

    expire_at: datetime
    url: str

    plan: "PlanSnapshotDto"

    created_at: Optional[datetime] = Field(default=None, frozen=True)
    updated_at: Optional[datetime] = Field(default=None, frozen=True)

    @property
    def is_active(self) -> bool:
        return self.status == SubscriptionStatus.ACTIVE

    @property
    def is_unlimited(self) -> bool:
        return self.expire_at.year == 2099

    @property
    def get_subscription_type(self) -> PlanType:
        has_traffic = self.traffic_limit > 0
        has_devices = self.device_limit > 0

        if has_traffic and has_devices:
            return PlanType.BOTH
        elif has_traffic:
            return PlanType.TRAFFIC
        elif has_devices:
            return PlanType.DEVICES
        else:
            return PlanType.UNLIMITED

    @property
    def has_devices_limit(self) -> bool:
        return self.get_subscription_type in (PlanType.DEVICES, PlanType.BOTH)

    @property
    def has_traffic_limit(self) -> bool:
        return self.get_subscription_type in (PlanType.TRAFFIC, PlanType.BOTH)

    def has_same_plan(self, plan: "PlanDto") -> bool:
        if plan is None or self.plan is None:
            return False

        return (
            self.plan.id == plan.id
            and self.plan.name == plan.name
            and self.plan.type == plan.type
            and self.plan.traffic_limit == plan.traffic_limit
            and self.plan.device_limit == plan.device_limit
            and self.plan.internal_squads == plan.internal_squads
        )

    def find_matching_plan(self, plans: list[PlanDto]) -> Optional[PlanDto]:
        return next((plan for plan in plans if self.has_same_plan(plan)), None)


class SubscriptionDto(BaseSubscriptionDto):
    user: Optional["BaseUserDto"] = None

    def apply_sync(self, sync_data: RemnaSubscriptionDto) -> SubscriptionDto:
        for field in type(sync_data).model_fields:
            if hasattr(self, field):
                old_value = getattr(self, field)
                new_value = getattr(sync_data, field)
                if old_value != new_value:
                    setattr(self, field, new_value)
                    logger.info(f"Field '{field}' updated: '{old_value}' → '{new_value}'")

        return self
