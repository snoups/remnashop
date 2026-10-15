import asyncio
import re
from typing import Any, Final, Optional

import httpx

from app.core.telegram_api import bot_file_url, bot_method_url
from app.modules.emoji_packs.dto import EmojiPackItemDto, FetchedEmojiPack

_TIMEOUT_S: Final[float] = 10.0
# t.me/addemoji/<name>, with or without scheme, query or trailing slash, or
# the bare name.
_SET_NAME_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:https?://)?(?:t\.me/addemoji/)?([A-Za-z0-9_]{1,64})/?(?:\?.*)?$"
)
_CUSTOM_EMOJI_TYPE: Final[str] = "custom_emoji"
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
    # Plain HTTP rather than aiogram: the api process does not install the
    # telegram extra, so importing Bot here would break it outright.
    async with httpx.AsyncClient(timeout=_TIMEOUT_S, proxy=proxy) as client:
        response = await client.post(
            bot_method_url(token, "getStickerSet"), json={"name": set_name}
        )
        payload = response.json()
        pack = parse_emoji_pack_payload(payload, set_name)
        artwork = await _download_artwork(client, token, payload["result"]["stickers"])

    return FetchedEmojiPack(
        set_name=pack.set_name,
        title=pack.title,
        items=[
            item.model_copy(update=artwork.get(item.custom_emoji_id, {})) for item in pack.items
        ],
    )


def parse_emoji_pack_payload(payload: dict, set_name: str) -> FetchedEmojiPack:
    if not payload.get("ok"):
        raise ValueError(payload.get("description") or "Telegram rejected the request")

    result = payload["result"]
    if result.get("sticker_type") != _CUSTOM_EMOJI_TYPE:
        raise ValueError(f"'{set_name}' is a sticker set, not an emoji pack")

    return FetchedEmojiPack(
        set_name=result["name"],
        title=result["title"],
        items=[
            EmojiPackItemDto(
                custom_emoji_id=sticker["custom_emoji_id"],
                # Telegram guarantees an emoji on a custom_emoji sticker, but a
                # missing one would only cost this entry its fallback glyph.
                fallback_emoji=sticker.get("emoji", ""),
            )
            for sticker in result.get("stickers", [])
            if sticker.get("custom_emoji_id")
        ],
    )


async def _download_artwork(
    client: httpx.AsyncClient, token: str, stickers: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    # Two files per emoji: the static .webp thumbnail any browser draws, and
    # the animation (gzipped lottie .tgs or .webm), which the dashboard plays
    # and an <img> can't.
    semaphore = asyncio.Semaphore(_DOWNLOAD_CONCURRENCY)

    async def download(file_id: Optional[str]) -> Optional[bytes]:
        if file_id is None:
            return None
        async with semaphore:
            try:
                info = await client.get(
                    bot_method_url(token, "getFile"), params={"file_id": file_id}
                )
                file_path = info.json()["result"]["file_path"]
                file = await client.get(bot_file_url(token, file_path))
                file.raise_for_status()
            except (httpx.HTTPError, KeyError):
                # Losing a file costs that emoji its artwork, not the import.
                return None
            return file.content

    async def artwork_of(sticker: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        thumbnail, animation = await asyncio.gather(
            download((sticker.get("thumbnail") or sticker.get("thumb") or {}).get("file_id")),
            download(sticker.get("file_id")),
        )
        return sticker["custom_emoji_id"], {
            "thumbnail": thumbnail,
            "animation": animation,
            "animation_kind": _animation_kind(animation),
        }

    downloaded = await asyncio.gather(
        *(artwork_of(sticker) for sticker in stickers if sticker.get("custom_emoji_id"))
    )
    return dict(downloaded)


def _animation_kind(animation: Optional[bytes]) -> Optional[str]:
    if animation is None:
        return None
    # A .tgs is gzipped lottie JSON, served as-is under Content-Encoding: gzip;
    # anything else Telegram hands back here is a .webm.
    return LOTTIE_KIND if animation.startswith(_GZIP_MAGIC) else VIDEO_KIND
