from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

if TYPE_CHECKING:
    from .plan import PlanSnapshotDto
    from .user import BaseUserDto

from datetime import datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, Field
from remnapy.enums import TrafficLimitStrategy

from src.core.enums import PlanType, SubscriptionStatus
from src.core.utils.formatters import (
    format_bytes_to_gb,
    format_device_count,
    i18n_format_expire_time,
)
from src.core.utils.time import datetime_now
from src.core.utils.types import RemnaUserDto

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
    def from_remna_user(cls, remna_user: RemnaUserDto) -> "RemnaSubscriptionDto":
        return cls(
            uuid=remna_user.uuid,
            status=remna_user.status,
            expire_at=remna_user.expire_at,
            url=remna_user.subscription_url,
            traffic_limit=format_bytes_to_gb(remna_user.traffic_limit_bytes),
            device_limit=format_device_count(remna_user.hwid_device_limit),
            traffic_limit_strategy=remna_user.traffic_limit_strategy,
            tag=remna_user.tag,
            internal_squads=[squad.uuid for squad in remna_user.active_internal_squads],
            external_squad=remna_user.external_squad_uuid,
        )


class BaseSubscriptionDto(TrackableDto):
    id: Optional[int] = Field(default=None, frozen=True)

    user_remna_id: UUID

    status: SubscriptionStatus = SubscriptionStatus.ACTIVE
    is_trial: bool = False

    traffic_limit: int
    device_limit: int
    traffic_limit_strategy: TrafficLimitStrategy

    tag: Optional[str] = None
    internal_squads: list[UUID]
    external_squad: Optional[UUID]

    expire_at: datetime
    url: str

    plan: "PlanSnapshotDto"

    created_at: Optional[datetime] = Field(default=None, frozen=True)
    updated_at: Optional[datetime] = Field(default=None, frozen=True)

    @property
    def is_active(self) -> bool:
        return self.get_status == SubscriptionStatus.ACTIVE

    @property
    def is_expired(self) -> bool:
        return self.get_status == SubscriptionStatus.EXPIRED

    @property
    def is_unlimited(self) -> bool:
        return self.expire_at.year == 2099

    @property
    def get_status(self) -> SubscriptionStatus:
        if datetime_now() > self.expire_at:
            return SubscriptionStatus.EXPIRED
        return self.status

    @property
    def get_traffic_reset_delta(self) -> Optional[timedelta]:
        from src.services.subscription import SubscriptionService  # noqa: PLC0415

        return SubscriptionService.get_traffic_reset_delta(self.traffic_limit_strategy)

    @property
    def get_expire_time(self) -> Union[list[tuple[str, dict[str, int]]], bool]:
        if self.get_traffic_reset_delta:
            return i18n_format_expire_time(self.get_traffic_reset_delta)
        else:
            return False

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


class SubscriptionDto(BaseSubscriptionDto):
    user: Optional["BaseUserDto"] = None
