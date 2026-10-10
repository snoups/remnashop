from datetime import datetime
from typing import Optional

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.core.enums import (
    BroadcastCategory,
    BroadcastMediaType,
    BroadcastRecipientStatus,
    BroadcastStatus,
    Locale,
)
from app.modules.broadcasts.dto import (
    BroadcastAudienceDto,
    BroadcastButtonDto,
    BroadcastContentDto,
)
from app.modules.broadcasts.validation import MAX_TITLE_LENGTH


class BroadcastRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = Field(default=None, max_length=MAX_TITLE_LENGTH)
    category: BroadcastCategory
    audience: BroadcastAudienceDto
    default_locale: Locale
    contents: dict[Locale, BroadcastContentDto] = Field(min_length=1)
    buttons: list[BroadcastButtonDto] = []
    promocode_id: Optional[int] = None
    post_to_channel: bool = False


class BroadcastResponse(BaseModel):
    id: int
    title: Optional[str] = None
    status: BroadcastStatus
    category: BroadcastCategory
    audience: BroadcastAudienceDto
    default_locale: Locale
    contents: dict[Locale, BroadcastContentDto]
    buttons: list[BroadcastButtonDto]
    promocode_id: Optional[int] = None
    post_to_channel: bool
    has_channel_post: bool
    recall_requested: bool
    recall_requested_at: Optional[datetime] = None
    recallable_count: Optional[int] = None
    media_type: Optional[BroadcastMediaType] = None
    media_size_bytes: Optional[int] = None
    scheduled_at: Optional[datetime] = None
    created_by: Optional[int] = None
    created_by_name: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_count: int
    sent_count: int
    failed_count: int
    blocked_count: int
    recalled_count: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BroadcastListResponse(BaseModel):
    items: list[BroadcastResponse]
    total: int


class BroadcastRecipientResponse(BaseModel):
    id: int
    user_id: int
    status: BroadcastRecipientStatus
    attempts: int
    error: Optional[str] = None
    sent_at: Optional[datetime] = None
    user_name: str
    username: Optional[str] = None
    telegram_id: Optional[int] = None
    language: Locale


class BroadcastRecipientListResponse(BaseModel):
    items: list[BroadcastRecipientResponse]
    total: int


class PreviewAudienceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audience: BroadcastAudienceDto
    category: BroadcastCategory


class AudiencePreviewResponse(BaseModel):
    total: int
    by_locale: dict[Locale, int]


class SendBroadcastRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scheduled_at: Optional[AwareDatetime] = None


class BroadcastSummaryResponse(BaseModel):
    by_status: dict[BroadcastStatus, int]
    next_scheduled_at: Optional[datetime] = None
    delivered_30d: int
    processed_30d: int
    opted_out: int
    reachable_customers: int
