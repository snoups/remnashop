from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from pydantic import Field

from src.core.enums import BroadcastAudience, BroadcastMessageStatus, BroadcastStatus
from src.core.utils.message_payload import MessagePayload
from src.core.utils.time import datetime_now

from .base import TrackableDto


class BroadcastDto(TrackableDto):
    id: Optional[int] = Field(default=None, frozen=True)
    task_id: UUID

    status: BroadcastStatus
    audience: BroadcastAudience

    total_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    payload: MessagePayload

    messages: Optional[list["BroadcastMessageDto"]] = []

    created_at: Optional[datetime] = Field(default=None, frozen=True)
    updated_at: Optional[datetime] = Field(default=None, frozen=True)

    @property
    def has_old(self) -> bool:
        if not self.created_at:
            return False
        return (
            self.status != BroadcastStatus.PROCESSING
            and datetime_now() - self.created_at > timedelta(days=7)
        )


class BroadcastMessageDto(TrackableDto):
    id: Optional[int] = Field(default=None, frozen=True)

    user_id: int
    message_id: Optional[int] = None

    status: BroadcastMessageStatus
