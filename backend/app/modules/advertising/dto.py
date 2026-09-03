from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Final, Optional

from pydantic import Field

from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import AdLinkChannel, Currency

DEFAULT_PAGE_SIZE: Final[int] = 50
MAX_PAGE_SIZE: Final[int] = 200


class AdLinkDto(BaseDto, TimestampMixin):
    name: str
    code: str
    cost: Decimal = Decimal(0)
    cost_currency: Currency = Currency.USD
    is_active: bool = True
    note: Optional[str] = None
    created_by: Optional[int] = None


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


class AdLinkStatsDto(BaseDto):
    attributions_count: int
    # A fraction in [0, 1], not a percentage -- callers multiply by 100 to display.
    conversion_rate: Decimal
    attributions_by_channel: dict[AdLinkChannel, int] = Field(default_factory=dict)
    paid_count: int
    revenue: Decimal
    revenue_by_currency: dict[Currency, Decimal] = Field(default_factory=dict)
    cost: Decimal
    report_currency: Currency
    cpa: Optional[Decimal] = None
    roi: Optional[Decimal] = None
    daily_registrations: list[DailyAttributionCountDto] = Field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class CreateAdLinkDto:
    name: str
    code: str
    cost: Decimal = Decimal(0)
    cost_currency: Currency = Currency.USD
    note: Optional[str] = None
    created_by: Optional[int] = None


@dataclass(frozen=True, kw_only=True)
class UpdateAdLinkDto:
    # None = leave unchanged, matching UpdatePromocodeDto's convention.
    ad_link_id: int
    name: Optional[str] = None
    cost: Optional[Decimal] = None
    cost_currency: Optional[Currency] = None
    is_active: Optional[bool] = None
    note: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class ListAdLinksDto:
    is_active: Optional[bool] = None
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


@dataclass(frozen=True, kw_only=True)
class GetAdLinkStatsDto:
    ad_link_id: int
    report_currency: Optional[Currency] = None


@dataclass(frozen=True, kw_only=True)
class ListAdLinkAttributedUsersDto:
    ad_link_id: int
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE
