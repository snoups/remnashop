from types import SimpleNamespace
from typing import Any

from app.core.enums import Locale
from app.telegram.i18n import build_translator_hub
from app.telegram.middlewares.requirements import channel_keyboard
from tests.seeded_translations import seeded_fluent_source


def _runner(locale: Locale) -> Any:
    hub = build_translator_hub([locale], {locale: seeded_fluent_source(locale, "menu.ftl")}, locale)
    return hub.get_translator_by_locale(locale.value)


def test_channel_buttons_carry_their_icons() -> None:
    requirements: Any = SimpleNamespace(channel_url="https://t.me/channel")

    keyboard = channel_keyboard(_runner(Locale.RU), requirements)

    assert [row[0].text for row in keyboard.inline_keyboard] == ["❤️ Подписаться", "✅ Я подписался"]
