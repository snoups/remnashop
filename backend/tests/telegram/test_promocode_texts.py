import html
from typing import Any

import pytest

from app.core.enums import Locale, PromocodeRewardType
from app.core.error_codes import ErrorCode
from app.core.utils.telegram_text import validate_telegram_html
from app.telegram.dialogs.rendering import render_window_text
from app.telegram.i18n import build_translator_hub
from tests.seeded_translations import seeded_fluent_source


def _confirm(locale: Locale, reward_type: PromocodeRewardType, amount: int, plan: str = "") -> str:
    hub = build_translator_hub([locale], {locale: seeded_fluent_source(locale, "menu.ftl")}, locale)
    runner: Any = hub.get_translator_by_locale(locale.value)
    return render_window_text(
        runner,
        "msg-promocode-confirm",
        promo_code="SALE",
        promo_reward_type=reward_type.value,
        promo_reward=amount,
        promo_plan_name=plan,
    )


@pytest.mark.parametrize("reward_type", list(PromocodeRewardType))
@pytest.mark.parametrize("locale", [Locale.RU, Locale.EN])
def test_every_reward_renders_valid_html(locale: Locale, reward_type: PromocodeRewardType) -> None:
    text = _confirm(locale, reward_type, 3, plan="Pro")

    validate_telegram_html(text, code=ErrorCode.TRANSLATION_HTML_INVALID)
    assert "<code>SALE</code>" in text
    assert "\n\n\n" not in text


def test_reward_amounts_and_warning() -> None:
    assert "<b>+50 ГБ</b> к лимиту трафика." in _confirm(Locale.RU, PromocodeRewardType.TRAFFIC, 50)
    assert "сгорит при смене тарифа" in _confirm(Locale.RU, PromocodeRewardType.DEVICES, 2)
    days = _confirm(Locale.RU, PromocodeRewardType.DURATION, 3)
    assert "<b>+3 дня</b> к сроку подписки." in days
    assert "сгорит" not in days
    plan = html.unescape(_confirm(Locale.RU, PromocodeRewardType.SUBSCRIPTION, 30, plan="Про"))
    assert "подписку <b>Про</b> на <b>30 дней</b>." in plan


@pytest.mark.parametrize(
    ("locale", "expected"),
    [
        (Locale.RU, "подписку <b>Про</b> <b>навсегда</b>."),
        (Locale.EN, "the <b>Про</b> subscription <b>forever</b>."),
    ],
)
def test_an_unlimited_subscription_reward_reads_forever(locale: Locale, expected: str) -> None:
    text = _confirm(locale, PromocodeRewardType.SUBSCRIPTION, 0, plan="Про")

    validate_telegram_html(text, code=ErrorCode.TRANSLATION_HTML_INVALID)
    assert expected in html.unescape(text)
