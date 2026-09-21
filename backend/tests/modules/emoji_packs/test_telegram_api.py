import pytest

from app.modules.emoji_packs.telegram_api import parse_emoji_pack_payload, parse_set_name


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


def test_parse_payload_keeps_id_and_fallback_glyph() -> None:
    pack = parse_emoji_pack_payload(
        {
            "ok": True,
            "result": {
                "name": "MemeEmoji",
                "title": "Meme Emoji",
                "sticker_type": "custom_emoji",
                "stickers": [
                    {"custom_emoji_id": "5386587088873331829", "emoji": "\U0001f604"},
                    # A plain sticker has no id and cannot be referenced at all.
                    {"emoji": "\U0001f605"},
                ],
            },
        },
        "MemeEmoji",
    )
    assert pack.set_name == "MemeEmoji"
    assert [(i.custom_emoji_id, i.fallback_emoji) for i in pack.items] == [
        ("5386587088873331829", "\U0001f604")
    ]


def test_parse_payload_rejects_a_plain_sticker_set() -> None:
    payload = {
        "ok": True,
        "result": {"name": "X", "title": "X", "sticker_type": "regular", "stickers": []},
    }
    with pytest.raises(ValueError, match="not an emoji pack"):
        parse_emoji_pack_payload(payload, "X")


def test_parse_payload_surfaces_the_telegram_error() -> None:
    with pytest.raises(ValueError, match="STICKERSET_INVALID"):
        parse_emoji_pack_payload({"ok": False, "description": "STICKERSET_INVALID"}, "X")
