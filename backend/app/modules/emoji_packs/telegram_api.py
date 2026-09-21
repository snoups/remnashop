import re
from typing import Final

import httpx

from app.modules.emoji_packs.dto import EmojiPackItemDto, FetchedEmojiPack

_TIMEOUT_S: Final[float] = 10.0
_API_URL: Final[str] = "https://api.telegram.org/bot{token}/getStickerSet"
# t.me/addemoji/<name>, with or without scheme, query or trailing slash -- or the
# bare name, which is what an admin who already knows it will paste.
_SET_NAME_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:https?://)?(?:t\.me/addemoji/)?([A-Za-z0-9_]{1,64})/?(?:\?.*)?$"
)
_CUSTOM_EMOJI_TYPE: Final[str] = "custom_emoji"


def parse_set_name(link: str) -> str:
    match = _SET_NAME_RE.match(link.strip())
    if match is None:
        raise ValueError(f"Not an emoji pack link: {link!r}")
    return match.group(1)


async def fetch_emoji_pack(token: str, set_name: str) -> FetchedEmojiPack:
    # Plain HTTP rather than aiogram: the api process does not install the
    # telegram extra, so importing Bot here would break it outright.
    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        response = await client.post(_API_URL.format(token=token), json={"name": set_name})

    return parse_emoji_pack_payload(response.json(), set_name)


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
