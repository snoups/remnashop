from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from app.core.enums import AdLinkChannel, Currency


class AdLinkResponse(BaseModel):
    id: int
    name: str
    code: str
    cost: Decimal
    cost_currency: Currency
    is_active: bool
    allow_bot: bool
    allow_webcabinet: bool
    note: Optional[str] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AdLinkPageResponse(BaseModel):
    items: list[AdLinkResponse]
    total: int


class CreateAdLinkRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=48, pattern=r"^[A-Za-z0-9_-]+$")
    cost: Decimal = Field(default=Decimal(0), ge=0)
    cost_currency: Currency = Currency.USD
    allow_bot: bool = True
    allow_webcabinet: bool = True
    note: Optional[str] = None


class UpdateAdLinkRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    cost: Optional[Decimal] = Field(default=None, ge=0)
    cost_currency: Optional[Currency] = None
    is_active: Optional[bool] = None
    allow_bot: Optional[bool] = None
    allow_webcabinet: Optional[bool] = None
    note: Optional[str] = None


class AdLinkShareUrlsResponse(BaseModel):
    bot_url: Optional[str] = None
    webcabinet_url: Optional[str] = None


class GeneratedAdLinkCodeResponse(BaseModel):
    code: str


class DailyAttributionCountResponse(BaseModel):
    day: date
    count: int
    by_channel: dict[AdLinkChannel, int]


class AdLinkStatsResponse(BaseModel):
    attributions_count: int
    attributions_by_channel: dict[AdLinkChannel, int]
    paid_count: int
    conversion_rate: Decimal
    revenue: Decimal
    revenue_by_currency: dict[Currency, Decimal]
    cost: Decimal
    report_currency: Currency
    cpa: Optional[Decimal] = None
    roi: Optional[Decimal] = None
    daily_registrations: list[DailyAttributionCountResponse]


class AdLinkMetricsResponse(BaseModel):
    ad_link_id: int
    attributions_count: int
    paid_count: int
    revenue: Decimal
    cost: Decimal
    roi: Optional[Decimal] = None


class AdvertisingSummaryResponse(BaseModel):
    report_currency: Currency
    attributions_count: int
    attributions_by_channel: dict[AdLinkChannel, int]
    paid_count: int
    conversion_rate: Decimal
    revenue: Decimal
    cost: Decimal
    cpa: Optional[Decimal] = None
    roi: Optional[Decimal] = None
    links: list[AdLinkMetricsResponse]


class AttributedUserResponse(BaseModel):
    user_id: int
    name: str
    channel: AdLinkChannel
    created_at: datetime
    has_paid: bool


class AttributedUserPageResponse(BaseModel):
    items: list[AttributedUserResponse]
    total: int


class UserAdAttributionResponse(BaseModel):
    ad_link_id: int
    name: str
    code: str
    channel: AdLinkChannel
    attributed_at: datetime
