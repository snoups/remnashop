from dataclasses import dataclass
from typing import Optional

from app.core.dto import BaseDto, TimestampMixin


class EmojiPackItemDto(BaseDto):
    custom_emoji_id: str
    fallback_emoji: str
    # Carried only on the import path and read back through their own
    # endpoints; a listing loads neither blob, only the kind.
    thumbnail: Optional[bytes] = None
    animation: Optional[bytes] = None
    animation_kind: Optional[str] = None


class EmojiPackDto(BaseDto, TimestampMixin):
    set_name: str
    title: str
    items: list[EmojiPackItemDto]


@dataclass(frozen=True, kw_only=True)
class FetchedEmojiPack:
    set_name: str
    title: str
    items: list[EmojiPackItemDto]
