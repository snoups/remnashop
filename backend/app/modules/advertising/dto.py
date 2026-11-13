from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import Field

from app.core.constants import DEFAULT_PAGE_SIZE, ZERO_AMOUNT
from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import AdLinkChannel, Currency
from app.core.utils.money import round_cents


class AdLinkDto(BaseDto, TimestampMixin):
    name: str
    code: str
    cost: Decimal = ZERO_AMOUNT
    cost_currency: Currency = Currency.USD
    revenue_share_percent: Decimal = ZERO_AMOUNT
    is_active: bool = True
    allow_bot: bool = True
    allow_webcabinet: bool = True
    note: Optional[str] = None
    created_by: Optional[int] = None

    def revenue_share(self, revenue: Decimal) -> Decimal:
        return round_cents(revenue * self.revenue_share_percent / 100)

    def allows(self, channel: AdLinkChannel) -> bool:
        return self.allow_bot if channel == AdLinkChannel.BOT else self.allow_webcabinet


class AdLinkAttributionDto(BaseDto):
    ad_link_id: int
    user_id: int
    channel: AdLinkChannel
    created_at: datetime


class AttributedUserDto(BaseDto):
    user_id: int
    name: str
    channel: AdLinkChannel
    created_at: datetime
    has_paid: bool


class DailyAttributionCountDto(BaseDto):
    day: date
    count: int
    by_channel: dict[AdLinkChannel, int] = Field(default_factory=dict)


class AdLinkStatsDto(BaseDto):
    attributions_count: int
    # a fraction in [0, 1], not a percentage
    conversion_rate: Decimal
    attributions_by_channel: dict[AdLinkChannel, int] = Field(default_factory=dict)
    paid_count: int
    revenue: Decimal
    # fixed_cost + revenue_share
    cost: Decimal
    fixed_cost: Decimal
    revenue_share_percent: Decimal
    revenue_share: Decimal
    report_currency: Currency
    cpa: Optional[Decimal] = None
    roi: Optional[Decimal] = None
    daily_registrations: list[DailyAttributionCountDto] = Field(default_factory=list)


class AdLinkMetricsDto(BaseDto):
    ad_link_id: int
    attributions_count: int
    paid_count: int
    revenue: Decimal
    cost: Decimal
    roi: Optional[Decimal] = None


class AdvertisingSummaryDto(BaseDto):
    report_currency: Currency
    attributions_count: int
    attributions_by_channel: dict[AdLinkChannel, int] = Field(default_factory=dict)
    paid_count: int
    conversion_rate: Decimal
    revenue: Decimal
    cost: Decimal
    cpa: Optional[Decimal] = None
    roi: Optional[Decimal] = None
    links: list[AdLinkMetricsDto] = Field(default_factory=list)


class AdLinkPayoutDto(BaseDto):
    report_currency: Currency
    payments_count: int
    revenue: Decimal
    revenue_share_percent: Decimal
    payout: Decimal


@dataclass(frozen=True, kw_only=True)
class CreateAdLinkDto:
    name: str
    code: str
    cost: Decimal = ZERO_AMOUNT
    cost_currency: Currency = Currency.USD
    revenue_share_percent: Decimal = ZERO_AMOUNT
    allow_bot: bool = True
    allow_webcabinet: bool = True
    note: Optional[str] = None
    created_by: Optional[int] = None


@dataclass(frozen=True, kw_only=True)
class UpdateAdLinkDto:
    # None = leave unchanged
    ad_link_id: int
    name: Optional[str] = None
    cost: Optional[Decimal] = None
    cost_currency: Optional[Currency] = None
    revenue_share_percent: Optional[Decimal] = None
    is_active: Optional[bool] = None
    allow_bot: Optional[bool] = None
    allow_webcabinet: Optional[bool] = None
    # "" clears the note
    note: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class ListAdLinksDto:
    is_active: Optional[bool] = None
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


@dataclass(frozen=True, kw_only=True)
class GetAdLinkStatsDto:
    ad_link_id: int
    # Counts only attributions made at or after this moment; None = all time.
    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None


@dataclass(frozen=True, kw_only=True)
class GetAdLinkPayoutDto:
    ad_link_id: int
    # payments made in [paid_from, paid_to) by everyone the link ever attributed
    paid_from: datetime
    paid_to: datetime


@dataclass(frozen=True, kw_only=True)
class GetAdvertisingSummaryDto:
    is_active: Optional[bool] = None
    created_from: Optional[datetime] = None
    # snapshot as of this moment: later attributions and payments are left out
    created_to: Optional[datetime] = None


@dataclass(frozen=True, kw_only=True)
class ListAdLinkAttributedUsersDto:
    ad_link_id: int
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


@dataclass(frozen=True, kw_only=True)
class UserAdAttributionDto:
    ad_link_id: int
    name: str
    code: str
    channel: AdLinkChannel
    attributed_at: datetime


@dataclass(frozen=True, kw_only=True)
class AdLinkShareUrlsDto:
    # None = channel not allowed on this link, or its base URL isn't known
    bot_url: Optional[str] = None
    webcabinet_url: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class RecordAdLinkAttributionDto:
    user_id: int
    ad_link_code: str
    channel: AdLinkChannel
