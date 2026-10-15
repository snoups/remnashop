from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SlideDto(BaseModel):
    image_url: Optional[str] = None
    text: dict[str, str]
    url: Optional[str] = None
    url_label: dict[str, str] = Field(default_factory=dict)


class AnnouncementDto(BaseModel):
    id: str
    icon: str
    severity: str
    title: dict[str, str]
    text: dict[str, str]
    url: Optional[str] = None
    url_label: dict[str, str] = Field(default_factory=dict)
    notify_at: datetime
    auto_open: bool
    slides: list[SlideDto]
    roles: Optional[list[str]] = None
    versions: Optional[str] = None
    # this actor's first view; None while unseen
    seen_at: Optional[datetime] = None
    # cleared from the bell by this actor
    dismissed_at: Optional[datetime] = None

    @property
    def seen(self) -> bool:
        return self.seen_at is not None


@dataclass(frozen=True, kw_only=True)
class AnnouncementIdsDto:
    ids: list[str]
