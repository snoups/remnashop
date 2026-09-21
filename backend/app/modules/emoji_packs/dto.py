from dataclasses import dataclass

from app.core.dto import BaseDto, TimestampMixin


class EmojiPackItemDto(BaseDto):
    custom_emoji_id: str
    fallback_emoji: str


class EmojiPackDto(BaseDto, TimestampMixin):
    set_name: str
    title: str
    items: list[EmojiPackItemDto]


@dataclass(frozen=True, kw_only=True)
class FetchedEmojiPack:
    set_name: str
    title: str
    items: list[EmojiPackItemDto]
