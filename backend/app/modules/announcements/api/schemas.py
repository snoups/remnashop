from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SlideResponse(BaseModel):
    image_url: Optional[str]
    text: dict[str, str]
    url: Optional[str]


class AnnouncementResponse(BaseModel):
    id: str
    icon: str
    severity: str
    title: dict[str, str]
    text: dict[str, str]
    url: Optional[str]
    notify_at: datetime
    auto_open: bool
    slides: list[SlideResponse]
    seen: bool


class AnnouncementListResponse(BaseModel):
    items: list[AnnouncementResponse]
    total: int


class MarkAnnouncementsSeenRequest(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=100)
