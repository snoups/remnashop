import re
from datetime import datetime
from typing import Final, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator

_EMAIL: Final[re.Pattern[str]] = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class NotificationChannelsResponse(BaseModel):
    channels: dict[str, list[str]]
    available_groups: list[str]
    available_channels: list[str]
    is_push_configured: bool
    telegram_available: bool


class UpdateNotificationChannelsRequest(BaseModel):
    channels: dict[str, list[str]]


class NotificationSettingsResponse(BaseModel):
    is_push_configured: bool
    vapid_public_key: Optional[str]
    vapid_contact: Optional[str]


class UpdateNotificationSettingsRequest(BaseModel):
    # an email, stored as the mailto: subject push services want (RFC 8292); can't be cleared
    vapid_contact: Optional[str] = Field(default=None, max_length=255)

    @field_validator("vapid_contact")
    @classmethod
    def email_to_mailto(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        email = value.strip().removeprefix("mailto:")
        if not _EMAIL.match(email):
            raise ValueError("vapid_contact must be an email")
        return f"mailto:{email}"


class PushPublicKeyResponse(BaseModel):
    public_key: Optional[str]


class PushSubscriptionKeysRequest(BaseModel):
    p256dh: str = Field(min_length=1, max_length=255)
    auth: str = Field(min_length=1, max_length=255)


class SubscribePushRequest(BaseModel):
    endpoint: HttpUrl
    keys: PushSubscriptionKeysRequest

    @field_validator("endpoint")
    @classmethod
    def https_only(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https":
            raise ValueError("endpoint must be https")
        return value


class PushSubscriptionResponse(BaseModel):
    id: int
    endpoint: str
    user_agent: Optional[str]
    created_at: datetime
    last_seen_at: datetime


class PushSubscriptionListResponse(BaseModel):
    items: list[PushSubscriptionResponse]
    total: int


class TestPushResponse(BaseModel):
    delivered: int
