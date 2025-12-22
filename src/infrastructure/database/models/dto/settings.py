from typing import Optional

from pydantic import Field

from .base import TrackableDto


class SettingsDto(TrackableDto):
    id: Optional[int] = Field(default=None, frozen=True)
