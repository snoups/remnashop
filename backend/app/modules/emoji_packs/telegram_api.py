import asyncio
import re
from typing import Any, Final, Optional

from app.core.telegram_api import BOT_API_ERRORS, BotApi, bot_api_error_text, bot_client
from app.modules.emoji_packs.dto import EmojiPackItemDto, FetchedEmojiPack

_TIMEOUT_S: Final[float] = 10.0
_CUSTOM_EMOJI: Final[str] = "custom_emoji"
# t.me/addemoji/<name>, with or without scheme, query or trailing slash, or
# the bare name.
_SET_NAME_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:https?://)?(?:t\.me/addemoji/)?([A-Za-z0-9_]{1,64})/?(?:\?.*)?$"
)
_DOWNLOAD_CONCURRENCY: Final[int] = 8
LOTTIE_KIND: Final[str] = "lottie"
VIDEO_KIND: Final[str] = "video"


def parse_set_name(link: str) -> str:
    match = _SET_NAME_RE.match(link.strip())
    if match is None:
        raise ValueError(f"Not an emoji pack link: {link!r}")
    return match.group(1)


async def fetch_emoji_pack(token: str, proxy: Optional[str], set_name: str) -> FetchedEmojiPack:
    try:
        async with bot_client(token, proxy, timeout=_TIMEOUT_S) as bot:
            sticker_set = await bot.call("getStickerSet", name=set_name)
            emoji = custom_emoji_stickers(sticker_set, set_name)
            semaphore = asyncio.Semaphore(_DOWNLOAD_CONCURRENCY)
            items = await asyncio.gather(
                *(_with_artwork(bot, semaphore, sticker, emoji_id) for sticker, emoji_id in emoji)
            )
    except BOT_API_ERRORS as error:
        raise ValueError(bot_api_error_text(error)) from error
    return FetchedEmojiPack(
        set_name=sticker_set["name"], title=sticker_set["title"], items=list(items)
    )


def custom_emoji_stickers(
    sticker_set: dict[str, Any], set_name: str
) -> list[tuple[dict[str, Any], str]]:
    """Each sticker that can be referenced, with its custom emoji id."""
    if sticker_set.get("sticker_type") != _CUSTOM_EMOJI:
        raise ValueError(f"'{set_name}' is a sticker set, not an emoji pack")
    return [
        (sticker, sticker["custom_emoji_id"])
        for sticker in sticker_set.get("stickers", [])
        if sticker.get("custom_emoji_id")
    ]


async def _with_artwork(
    bot: BotApi, semaphore: asyncio.Semaphore, sticker: dict[str, Any], custom_emoji_id: str
) -> EmojiPackItemDto:
    # Two files per animated emoji: the static .webp thumbnail any browser
    # draws, and the animation (gzipped lottie .tgs or .webm), which the
    # dashboard plays and an <img> can't. A static emoji is a .webp itself.
    kind = _animation_kind(sticker)
    thumbnail = sticker.get("thumbnail")
    thumbnail_id: Optional[str] = thumbnail["file_id"] if thumbnail else None
    animation_id: Optional[str] = sticker["file_id"]
    if kind is None:
        thumbnail_id, animation_id = sticker["file_id"], None
    thumbnail_file, animation = await asyncio.gather(
        _download(bot, semaphore, thumbnail_id), _download(bot, semaphore, animation_id)
    )
    return EmojiPackItemDto(
        custom_emoji_id=custom_emoji_id,
        # Telegram guarantees an emoji on a custom_emoji sticker, but a missing
        # one would only cost this entry its fallback glyph.
        fallback_emoji=sticker.get("emoji") or "",
        thumbnail=thumbnail_file,
        animation=animation,
        animation_kind=kind if animation is not None else None,
    )


async def _download(
    bot: BotApi, semaphore: asyncio.Semaphore, file_id: Optional[str]
) -> Optional[bytes]:
    if file_id is None:
        return None
    async with semaphore:
        try:
            return await bot.download(file_id)
        except BOT_API_ERRORS:
            # Losing a file costs that emoji its artwork, not the import.
            return None


def _animation_kind(sticker: dict[str, Any]) -> Optional[str]:
    if sticker.get("is_animated"):
        return LOTTIE_KIND
    return VIDEO_KIND if sticker.get("is_video") else None
