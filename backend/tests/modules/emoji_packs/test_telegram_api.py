from typing import Optional

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.methods import GetFile, GetStickerSet
from aiogram.types import File, PhotoSize, Sticker, StickerSet

from app.modules.emoji_packs.telegram_api import (
    custom_emoji_stickers,
    fetch_emoji_pack,
    parse_set_name,
)
from tests.fakes.telegram_bot import FakeBotSession, use_fake_bot


@pytest.mark.parametrize(
    "link",
    [
        "https://t.me/addemoji/MemeEmoji",
        "http://t.me/addemoji/MemeEmoji",
        "t.me/addemoji/MemeEmoji",
        "t.me/addemoji/MemeEmoji/",
        "  https://t.me/addemoji/MemeEmoji?startapp=1  ",
        "MemeEmoji",
    ],
)
def test_parse_set_name_accepts_every_shape_an_admin_might_paste(link: str) -> None:
    assert parse_set_name(link) == "MemeEmoji"


@pytest.mark.parametrize("link", ["", "https://example.com/addemoji/X", "t.me/addstickers/X"])
def test_parse_set_name_rejects_anything_else(link: str) -> None:
    with pytest.raises(ValueError):
        parse_set_name(link)


def _sticker(emoji_id: Optional[str], file_id: str, thumb_id: Optional[str] = None) -> Sticker:
    return Sticker(
        file_id=file_id,
        file_unique_id=f"u{file_id}",
        type="custom_emoji" if emoji_id else "regular",
        width=100,
        height=100,
        is_animated=True,
        is_video=False,
        emoji="\U0001f604",
        custom_emoji_id=emoji_id,
        thumbnail=PhotoSize(file_id=thumb_id, file_unique_id=f"u{thumb_id}", width=1, height=1)
        if thumb_id
        else None,
    )


def _set(sticker_type: str, stickers: list[Sticker]) -> StickerSet:
    return StickerSet(
        name="MemeEmoji", title="Meme Emoji", sticker_type=sticker_type, stickers=stickers
    )


def test_only_stickers_with_an_emoji_id_are_kept() -> None:
    kept = custom_emoji_stickers(
        # a plain sticker has no id and cannot be referenced at all
        _set("custom_emoji", [_sticker("5386587088873331829", "a"), _sticker(None, "b")]),
        "MemeEmoji",
    )

    assert [emoji_id for _, emoji_id in kept] == ["5386587088873331829"]


def test_a_plain_sticker_set_is_refused() -> None:
    with pytest.raises(ValueError, match="not an emoji pack"):
        custom_emoji_stickers(_set("regular", []), "X")


def _file(method: GetFile) -> File:
    return File(file_id=method.file_id, file_unique_id="u", file_path=f"files/{method.file_id}")


async def test_fetch_keeps_artwork_and_survives_a_failed_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _get_file(method: GetFile) -> object:
        if method.file_id == "broken":
            return TelegramBadRequest(method=method, message="file is too big")
        return _file(method)

    sticker_set = _set(
        "custom_emoji", [_sticker("1", "anim1", "thumb1"), _sticker("2", "broken", "thumb2")]
    )
    use_fake_bot(
        monkeypatch,
        FakeBotSession(
            {"GetStickerSet": sticker_set, "GetFile": _get_file},
            files={
                "files/anim1": b"\x1f\x8bgz",
                "files/thumb1": b"webp1",
                "files/thumb2": b"webp2",
            },
        ),
    )

    pack = await fetch_emoji_pack("123:abc", None, "MemeEmoji")

    first, second = pack.items
    assert (first.thumbnail, first.animation, first.animation_kind) == (
        b"webp1",
        b"\x1f\x8bgz",
        "lottie",
    )
    assert (second.thumbnail, second.animation, second.animation_kind) == (b"webp2", None, None)


async def test_an_unreachable_telegram_is_a_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    down = TelegramNetworkError(method=GetStickerSet(name="X"), message="timeout")
    use_fake_bot(monkeypatch, FakeBotSession({"GetStickerSet": down}))

    with pytest.raises(ValueError, match="timeout"):
        await fetch_emoji_pack("123:abc", None, "X")
