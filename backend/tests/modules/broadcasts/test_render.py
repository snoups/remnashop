from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.enums import (
    BroadcastButtonKind,
    BroadcastCategory,
    BroadcastMediaType,
    BroadcastStatus,
    Locale,
)
from app.modules.broadcasts.dto import (
    BroadcastAudienceDto,
    BroadcastButtonDto,
    BroadcastContentDto,
    BroadcastDto,
    RecipientContextDto,
)
from app.modules.broadcasts.render import BroadcastRenderer, outgoing_media

NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)


def _broadcast(**overrides: object) -> BroadcastDto:
    values: dict[str, object] = {
        "id": 7,
        "status": BroadcastStatus.SENDING,
        "category": BroadcastCategory.SERVICE,
        "audience": BroadcastAudienceDto(),
        "default_locale": Locale.EN,
        "contents": {
            Locale.EN: BroadcastContentDto(
                text="Hi { $name }, { $days_left } days, code { $promocode }",
                button_labels=["Site", "Get", "Menu"],
            ),
            Locale.RU: BroadcastContentDto(
                text="Привет, { $name }", button_labels=["Сайт", "Забрать", "Меню"]
            ),
        },
        "buttons": [
            BroadcastButtonDto(kind=BroadcastButtonKind.URL, url="https://x.y"),
            BroadcastButtonDto(kind=BroadcastButtonKind.PROMOCODE),
            BroadcastButtonDto(kind=BroadcastButtonKind.MENU),
        ],
        "promocode_id": 3,
    }
    values.update(overrides)
    return BroadcastDto(**values)  # type: ignore[arg-type]


def _ctx(language: Locale = Locale.EN, **overrides: object) -> RecipientContextDto:
    values: dict[str, object] = {
        "user_id": 1,
        "name": "Ann",
        "username": None,
        "language": language,
        "bonus_days": 0,
        "points": 0,
        "plan_name": "Pro",
        "expire_at": NOW + timedelta(days=3, hours=1),
    }
    values.update(overrides)
    return RecipientContextDto(**values)  # type: ignore[arg-type]


def _texts(markup: dict) -> list[str]:
    return [row[0]["text"] for row in markup["inline_keyboard"]]


def test_renders_variables_and_buttons() -> None:
    message = BroadcastRenderer(_broadcast(), promocode_code="SALE", unsubscribe_labels={}).render(
        _ctx(), NOW
    )
    assert message.text == "Hi Ann, 3 days, code SALE"
    assert message.reply_markup is not None
    rows = message.reply_markup["inline_keyboard"]
    assert rows[0][0] == {"text": "Site", "url": "https://x.y"}
    assert rows[1][0] == {"text": "Get", "callback_data": "bc:promo:7"}
    assert rows[2][0] == {"text": "Menu", "callback_data": "bc:menu"}


def test_locale_variant_and_fallback() -> None:
    renderer = BroadcastRenderer(_broadcast(), promocode_code="SALE", unsubscribe_labels={})
    assert renderer.render(_ctx(Locale.RU), NOW).text == "Привет, Ann"
    fallback = renderer.render(_ctx(Locale.DE), NOW)
    assert fallback.text.startswith("Hi Ann") and _texts(fallback.reply_markup or {})[0] == "Site"


def test_dropped_promocode_removes_button_and_value() -> None:
    message = BroadcastRenderer(_broadcast(), promocode_code=None, unsubscribe_labels={}).render(
        _ctx(), NOW
    )
    assert message.text.endswith("code —")
    assert "Get" not in _texts(message.reply_markup or {})


def test_marketing_adds_unsubscribe_last() -> None:
    renderer = BroadcastRenderer(
        _broadcast(category=BroadcastCategory.MARKETING),
        promocode_code="SALE",
        unsubscribe_labels={Locale.EN: "Unsubscribe", Locale.RU: "Отписаться"},
    )
    rows = (renderer.render(_ctx(Locale.RU), NOW).reply_markup or {})["inline_keyboard"]
    assert rows[-1][0] == {"text": "Отписаться", "callback_data": "bc:unsub"}
    channel_rows = (renderer.render_channel("shop_bot").reply_markup or {})["inline_keyboard"]
    assert all(row[0].get("callback_data") != "bc:unsub" for row in channel_rows)


def test_no_buttons_means_no_markup() -> None:
    broadcast = _broadcast(
        buttons=[], contents={Locale.EN: BroadcastContentDto(text="x")}, promocode_id=None
    )
    assert (
        BroadcastRenderer(broadcast, promocode_code=None, unsubscribe_labels={})
        .render(_ctx(), NOW)
        .reply_markup
        is None
    )


def test_channel_post_uses_deep_links() -> None:
    renderer = BroadcastRenderer(_broadcast(), promocode_code="SALE", unsubscribe_labels={})
    rows = (renderer.render_channel("shop_bot").reply_markup or {})["inline_keyboard"]
    assert rows[0][0] == {"text": "Site", "url": "https://x.y"}
    assert rows[1][0] == {"text": "Get", "url": "https://t.me/shop_bot?start=bc_7"}
    assert rows[2][0] == {"text": "Menu", "url": "https://t.me/shop_bot?start=menu"}


def test_channel_post_without_username_omits_bot_buttons() -> None:
    renderer = BroadcastRenderer(_broadcast(), promocode_code="SALE", unsubscribe_labels={})
    assert _texts(renderer.render_channel(None).reply_markup or {}) == ["Site"]


def test_outgoing_media_path_includes_the_version() -> None:
    broadcast = _broadcast(
        media_type=BroadcastMediaType.PHOTO, media_extension="jpg", media_version=3
    )
    media = outgoing_media(Path("/media"), broadcast)
    assert media is not None
    assert media.path == Path("/media/broadcasts/7_3.jpg")
