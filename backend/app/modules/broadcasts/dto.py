from dataclasses import dataclass, field
from datetime import datetime
from typing import Final, Optional

from pydantic import BaseModel, ConfigDict

from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import (
    BroadcastButtonKind,
    BroadcastCategory,
    BroadcastMediaType,
    BroadcastRecipientStatus,
    BroadcastStatus,
    BroadcastSubscriptionFilter,
    Locale,
)

DEFAULT_PAGE_SIZE: Final[int] = 20
MAX_PAGE_SIZE: Final[int] = 100


class BroadcastAudienceDto(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    user_ids: list[int] = []
    subscription: list[BroadcastSubscriptionFilter] = []
    plan_ids: list[int] = []
    expires_within_days: Optional[int] = None
    expired_within_days: Optional[int] = None
    paid: Optional[bool] = None
    locales: list[Locale] = []
    registered_from: Optional[datetime] = None
    registered_to: Optional[datetime] = None
    ad_link_ids: list[int] = []
    referred: Optional[bool] = None


class BroadcastButtonDto(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: BroadcastButtonKind
    url: Optional[str] = None


class BroadcastContentDto(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    button_labels: list[str] = []


class BroadcastDto(BaseDto, TimestampMixin):
    title: Optional[str] = None
    status: BroadcastStatus
    category: BroadcastCategory
    audience: BroadcastAudienceDto
    default_locale: Locale
    contents: dict[Locale, BroadcastContentDto]
    buttons: list[BroadcastButtonDto]
    promocode_id: Optional[int] = None
    post_to_channel: bool = False
    channel_chat_id: Optional[int] = None
    channel_message_id: Optional[int] = None
    media_type: Optional[BroadcastMediaType] = None
    media_content_type: Optional[str] = None
    media_extension: Optional[str] = None
    media_version: int = 0
    media_size_bytes: Optional[int] = None
    media_file_id: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    created_by: Optional[int] = None
    created_by_name: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    recall_requested_at: Optional[datetime] = None
    total_count: int = 0
    sent_count: int = 0
    failed_count: int = 0
    blocked_count: int = 0
    recalled_count: int = 0

    @property
    def has_media(self) -> bool:
        return self.media_type is not None

    @property
    def recall_requested(self) -> bool:
        return self.recall_requested_at is not None

    @property
    def has_channel_post(self) -> bool:
        return self.channel_message_id is not None


class BroadcastRecipientDto(BaseDto):
    broadcast_id: int
    user_id: int
    status: BroadcastRecipientStatus
    attempts: int
    telegram_message_id: Optional[int] = None
    error: Optional[str] = None
    sent_at: Optional[datetime] = None
    user_name: str
    username: Optional[str] = None
    telegram_id: Optional[int] = None
    language: Locale


@dataclass(frozen=True, kw_only=True)
class PendingRecipientDto:
    id: int
    user_id: int
    telegram_id: int
    attempts: int


@dataclass(frozen=True, kw_only=True)
class SentRecipientDto:
    id: int
    telegram_id: int
    telegram_message_id: int


@dataclass(frozen=True, kw_only=True)
class RecipientContextDto:
    user_id: int
    name: str
    username: Optional[str]
    language: Locale
    bonus_days: int
    points: int
    plan_name: Optional[str]
    expire_at: Optional[datetime]


@dataclass(frozen=True, kw_only=True)
class SaveBroadcastDto:
    category: BroadcastCategory
    audience: BroadcastAudienceDto
    default_locale: Locale
    contents: dict[Locale, BroadcastContentDto]
    buttons: list[BroadcastButtonDto]
    promocode_id: Optional[int]
    post_to_channel: bool
    title: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class UpdateBroadcastDto:
    broadcast_id: int
    data: SaveBroadcastDto


@dataclass(frozen=True, kw_only=True)
class ListBroadcastsDto:
    statuses: list[BroadcastStatus] = field(default_factory=list)
    search: Optional[str] = None
    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


@dataclass(frozen=True, kw_only=True)
class ListBroadcastRecipientsDto:
    broadcast_id: int
    status: Optional[BroadcastRecipientStatus] = None
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


@dataclass(frozen=True, kw_only=True)
class PreviewAudienceDto:
    audience: BroadcastAudienceDto
    category: BroadcastCategory


@dataclass(frozen=True, kw_only=True)
class AudiencePreviewDto:
    total: int
    by_locale: dict[Locale, int]


@dataclass(frozen=True, kw_only=True)
class SetBroadcastMediaDto:
    broadcast_id: int
    content_type: str
    data: bytes


@dataclass(frozen=True, kw_only=True)
class SendBroadcastDto:
    broadcast_id: int
    scheduled_at: Optional[datetime] = None


@dataclass(frozen=True, kw_only=True)
class BroadcastSummaryDto:
    by_status: dict[BroadcastStatus, int]
    next_scheduled_at: Optional[datetime]
    delivered_30d: int
    processed_30d: int
    opted_out: int
    reachable_customers: int
