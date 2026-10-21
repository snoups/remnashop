import asyncio
import re
from typing import Final, Optional

from aiogram import Bot
from aiogram.enums import StickerType
from aiogram.types import Sticker, StickerSet

from app.core.telegram_api import BOT_API_ERRORS, bot_api_error_text, bot_client
from app.modules.emoji_packs.dto import EmojiPackItemDto, FetchedEmojiPack

_TIMEOUT_S: Final[float] = 10.0
# t.me/addemoji/<name>, with or without scheme, query or trailing slash, or
# the bare name.
_SET_NAME_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:https?://)?(?:t\.me/addemoji/)?([A-Za-z0-9_]{1,64})/?(?:\?.*)?$"
)
_DOWNLOAD_CONCURRENCY: Final[int] = 8
_GZIP_MAGIC: Final[bytes] = b"\x1f\x8b"
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
            sticker_set = await bot.get_sticker_set(name=set_name)
            emoji = custom_emoji_stickers(sticker_set, set_name)
            semaphore = asyncio.Semaphore(_DOWNLOAD_CONCURRENCY)
            items = await asyncio.gather(
                *(_with_artwork(bot, semaphore, sticker, emoji_id) for sticker, emoji_id in emoji)
            )
    except BOT_API_ERRORS as error:
        raise ValueError(bot_api_error_text(error)) from error
    return FetchedEmojiPack(set_name=sticker_set.name, title=sticker_set.title, items=list(items))


def custom_emoji_stickers(sticker_set: StickerSet, set_name: str) -> list[tuple[Sticker, str]]:
    """Each sticker that can be referenced, with its custom emoji id."""
    if sticker_set.sticker_type != StickerType.CUSTOM_EMOJI:
        raise ValueError(f"'{set_name}' is a sticker set, not an emoji pack")
    return [
        (sticker, sticker.custom_emoji_id)
        for sticker in sticker_set.stickers
        if sticker.custom_emoji_id
    ]


async def _with_artwork(
    bot: Bot, semaphore: asyncio.Semaphore, sticker: Sticker, custom_emoji_id: str
) -> EmojiPackItemDto:
    # Two files per emoji: the static .webp thumbnail any browser draws, and
    # the animation (gzipped lottie .tgs or .webm), which the dashboard plays
    # and an <img> can't.
    thumbnail_id = sticker.thumbnail.file_id if sticker.thumbnail else None
    thumbnail, animation = await asyncio.gather(
        _download(bot, semaphore, thumbnail_id), _download(bot, semaphore, sticker.file_id)
    )
    return EmojiPackItemDto(
        custom_emoji_id=custom_emoji_id,
        # Telegram guarantees an emoji on a custom_emoji sticker, but a missing
        # one would only cost this entry its fallback glyph.
        fallback_emoji=sticker.emoji or "",
        thumbnail=thumbnail,
        animation=animation,
        animation_kind=_animation_kind(animation),
    )


async def _download(
    bot: Bot, semaphore: asyncio.Semaphore, file_id: Optional[str]
) -> Optional[bytes]:
    if file_id is None:
        return None
    async with semaphore:
        try:
            content = await bot.download(file_id)
        except BOT_API_ERRORS:
            # Losing a file costs that emoji its artwork, not the import.
            return None
    return content.read() if content is not None else None


def _animation_kind(animation: Optional[bytes]) -> Optional[str]:
    if animation is None:
        return None
    # A .tgs is gzipped lottie JSON, served as-is under Content-Encoding: gzip;
    # anything else Telegram hands back here is a .webm.
    return LOTTIE_KIND if animation.startswith(_GZIP_MAGIC) else VIDEO_KIND
