from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


class NotificationChannelsResponse(BaseModel):
    channels: dict[str, list[str]]
    available_groups: list[str]
    available_channels: list[str]
    push_configured: bool
    telegram_available: bool


class UpdateNotificationChannelsRequest(BaseModel):
    channels: dict[str, list[str]]


class NotificationSettingsResponse(BaseModel):
    is_push_configured: bool
    vapid_public_key: Optional[str]
    vapid_contact: Optional[str]


class UpdateNotificationSettingsRequest(BaseModel):
    # empty string clears it
    vapid_contact: Optional[str] = Field(
        default=None, max_length=255, pattern=r"^(mailto:[^@\s]+@[^@\s]+|https://\S+)?$"
    )

    @field_validator("vapid_contact", mode="before")
    @classmethod
    def plain_email_to_mailto(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        value = value.strip()
        if "@" in value and not value.startswith(("mailto:", "https://")):
            return f"mailto:{value}"
        return value


class PushPublicKeyResponse(BaseModel):
    public_key: Optional[str]


class PushSubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=1, max_length=255)
    auth: str = Field(min_length=1, max_length=255)


class SubscribePushRequest(BaseModel):
    endpoint: HttpUrl
    keys: PushSubscriptionKeys

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
