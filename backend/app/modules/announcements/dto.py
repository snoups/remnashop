from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SlideDto(BaseModel):
    image_url: Optional[str] = None
    text: dict[str, str]
    url: Optional[str] = None


class AnnouncementDto(BaseModel):
    id: str
    icon: str
    severity: str
    title: dict[str, str]
    text: dict[str, str]
    url: Optional[str] = None
    notify_at: datetime
    auto_open: bool
    slides: list[SlideDto]
    roles: Optional[list[str]] = None
    versions: Optional[str] = None
    # this actor's first view; None while unseen
    seen_at: Optional[datetime] = None

    @property
    def seen(self) -> bool:
        return self.seen_at is not None
