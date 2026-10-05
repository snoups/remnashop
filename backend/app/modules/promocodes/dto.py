from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Final, Optional

from pydantic import Field

from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import Currency, PromocodeAvailability, PromocodeRewardType, PromocodeStatus

DEFAULT_PAGE_SIZE: Final[int] = 50
MAX_PAGE_SIZE: Final[int] = 200


class PromocodeDto(BaseDto, TimestampMixin):
    code: str
    is_active: bool
    reward_type: PromocodeRewardType
    reward: Optional[int] = None
    reward_addon_id: Optional[int] = None
    reward_plan_id: Optional[int] = None
    reward_duration_days: Optional[int] = None
    availability: PromocodeAvailability = PromocodeAvailability.ALL
    allowed_user_ids: list[int] = Field(default_factory=list)
    allowed_plan_ids: list[int] = Field(default_factory=list)
    expires_at: Optional[datetime] = None
    max_activations: Optional[int] = None
    is_reusable: bool = False


class PromocodeActivationDto(BaseDto):
    promocode_id: int
    user_id: int
    subscription_id: Optional[int] = None
    activated_at: datetime


@dataclass(frozen=True, kw_only=True)
class CreatePromocodeDto:
    code: str
    reward_type: PromocodeRewardType
    reward: Optional[int] = None
    reward_addon_id: Optional[int] = None
    reward_plan_id: Optional[int] = None
    reward_duration_days: Optional[int] = None
    availability: PromocodeAvailability = PromocodeAvailability.ALL
    allowed_user_ids: list[int] = field(default_factory=list)
    allowed_plan_ids: list[int] = field(default_factory=list)
    expires_at: Optional[datetime] = None
    max_activations: Optional[int] = None
    is_reusable: bool = False


@dataclass(frozen=True, kw_only=True)
class UpdatePromocodeDto:
    promocode_id: int
    is_active: Optional[bool] = None
    availability: Optional[PromocodeAvailability] = None
    allowed_user_ids: Optional[list[int]] = None
    allowed_plan_ids: Optional[list[int]] = None
    expires_at: Optional[datetime] = None
    max_activations: Optional[int] = None
    is_reusable: Optional[bool] = None


@dataclass(frozen=True, kw_only=True)
class ActivatePromocodeDto:
    code: str
    target_subscription_id: Optional[int] = None


@dataclass(frozen=True, kw_only=True)
class UserPromocodeActivationDto:
    activation_id: int
    promocode_id: int
    code: str
    reward_type: PromocodeRewardType
    reward: Optional[int]
    reward_duration_days: Optional[int]
    activated_at: datetime


@dataclass(frozen=True, kw_only=True)
class PromocodeSummaryDto:
    total_count: int
    active_count: int
    activations_count: int
    activated_users_count: int
    activations_by_promocode: dict[int, int]
    granted_days: int
    granted_subscriptions_count: int
    report_currency: Currency
    discount_amount: Decimal
    discounted_orders_count: int


@dataclass(frozen=True, kw_only=True)
class PromocodeRewardTotalsDto:
    count: int
    reward_sum: int
    duration_days_sum: int


@dataclass(frozen=True, kw_only=True)
class ListPromocodesDto:
    status: Optional[PromocodeStatus] = None
    reward_type: Optional[PromocodeRewardType] = None
    search: Optional[str] = None
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


@dataclass(frozen=True, kw_only=True)
class ListPromocodeActivatedUsersDto:
    promocode_id: int
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


@dataclass(frozen=True, kw_only=True)
class PromocodeActivatedUserDto:
    activation_id: int
    user_id: int
    name: str
    subscription_id: Optional[int]
    activated_at: datetime


@dataclass(frozen=True, kw_only=True)
class ValidatePromocodeDto:
    code: str
