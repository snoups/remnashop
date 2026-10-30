from datetime import datetime

from pydantic import BaseModel


class CustomerFeedItemResponse(BaseModel):
    id: int
    event_type: str
    title: str
    body: str
    url: str
    created_at: datetime
    read: bool


class CustomerFeedResponse(BaseModel):
    items: list[CustomerFeedItemResponse]
    unread_count: int
