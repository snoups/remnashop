from typing import Optional

from pydantic import BaseModel, Field


class EmojiPackItemResponse(BaseModel):
    custom_emoji_id: str
    fallback_emoji: str
    # "lottie", "video", or null when this emoji has no animation stored.
    animation_kind: Optional[str]


class EmojiPackResponse(BaseModel):
    set_name: str
    title: str
    items: list[EmojiPackItemResponse]


class ImportEmojiPackRequest(BaseModel):
    link: str = Field(min_length=1, max_length=256)


class EmojiPackListResponse(BaseModel):
    items: list[EmojiPackResponse]
    total: int
