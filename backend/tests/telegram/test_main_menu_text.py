from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
from remnapy.enums import TrafficLimitStrategy

from app.core.constants import USER_KEY
from app.core.enums import Locale, SubscriptionStatus
from app.core.error_codes import ErrorCode
from app.core.utils.telegram_text import validate_telegram_html
from app.modules.dialogs import catalog
from app.modules.dialogs.flows.menu import register_menu_metadata
from app.telegram.dialogs.rendering import render_window_text
from app.telegram.i18n import build_translator_hub
from app.telegram.routers.menu.getters import (
    menu_getter,
    menu_subscription,
    subscription_menu_values,
)
from tests.seeded_translations import seeded_fluent_source


def _runner(locale: Locale) -> Any:
    hub = build_translator_hub([locale], {locale: seeded_fluent_source(locale, "menu.ftl")}, locale)
    return hub.get_translator_by_locale(locale.value)


def _subscription(status: str, **overrides: Any) -> Optional[SimpleNamespace]:
    if status == "NONE":
        return None
    values: dict[str, Any] = {
        "status": SubscriptionStatus(status),
        "is_trial": False,
        "traffic_limit_strategy": TrafficLimitStrategy.NO_RESET,
        "effective_traffic_limit": 100,
        "effective_device_limit": 3,
        "expire_at": datetime(2027, 1, 1, 12, 0, tzinfo=timezone.utc),
    }
    return SimpleNamespace(**{**values, **overrides})


def _menu(
    locale: Locale = Locale.RU,
    status: str = "ACTIVE",
    *,
    extra_count: int = 0,
    trial_available: bool = False,
    subscription: Optional[dict[str, Any]] = None,
    **kwargs: Any,
) -> str:
    runner = _runner(locale)
    values = subscription_menu_values(
        runner,
        _subscription(status, **(subscription or {})),
        extra_count=extra_count,
        trial_available=trial_available,
    )
    args = {"user_id": "123456789", "user_name": "Ivan", "user_discount": "", **values, **kwargs}
    text = render_window_text(runner, "msg-main-menu", **args)
    return text.replace("\u2068", "").replace("\u2069", "")


@pytest.mark.parametrize(
    "strategy", [TrafficLimitStrategy.NO_RESET, TrafficLimitStrategy.MONTH], ids=lambda s: s.value
)
@pytest.mark.parametrize("is_trial", [False, True])
@pytest.mark.parametrize("status", ["ACTIVE", "LIMITED", "EXPIRED", "DISABLED", "NONE"])
@pytest.mark.parametrize("locale", [Locale.RU, Locale.EN])
def test_default_menu_is_valid_html_for_every_state(
    status: str, locale: Locale, is_trial: bool, strategy: TrafficLimitStrategy
) -> None:
    subscription = {"is_trial": is_trial, "traffic_limit_strategy": strategy}
    for kwargs in ({"user_id": "", "user_discount": ""}, {"user_discount": "15"}):
        text = _menu(locale, status, extra_count=2, subscription=subscription, **kwargs)
        validate_telegram_html(text, code=ErrorCode.TRANSLATION_HTML_INVALID)


def test_active_block_shows_limits_and_expiry() -> None:
    text = _menu()

    assert "💳 Подписка" in text
    assert "100 ГБ" in text
    assert "01.01.2027" in text


def test_unlimited_limits_read_as_unlimited() -> None:
    runner = _runner(Locale.EN)
    subscription = _subscription("ACTIVE", effective_traffic_limit=0, effective_device_limit=0)

    values = subscription_menu_values(runner, subscription, extra_count=0, trial_available=False)

    assert values["subscription_traffic_limit"] == "Unlimited"
    assert values["subscription_device_limit"] == "Unlimited"
    assert values["subscription_status"] == "Active"


def test_limits_are_not_grouped() -> None:
    runner = _runner(Locale.RU)
    subscription = _subscription("ACTIVE", effective_traffic_limit=1000)

    values = subscription_menu_values(runner, subscription, extra_count=0, trial_available=False)

    assert "1000" in values["subscription_traffic_limit"]


def test_trial_header_and_none_texts() -> None:
    runner = _runner(Locale.RU)
    trial = subscription_menu_values(
        runner, _subscription("ACTIVE", is_trial=True), extra_count=0, trial_available=False
    )
    assert "🎁 Пробная подписка" in trial["subscription_block"]

    none = _menu(status="NONE")
    assert "Купить подписку" in none
    assert "💳 Подписка" not in none
    assert "• У вас нет" not in none
    assert "<blockquote>У вас нет оформленной подписки." in none
    assert "пробник" in _menu(status="NONE", trial_available=True)


def test_menu_escapes_user_name() -> None:
    text = _menu(user_name="<b>&")

    assert "&lt;b&gt;&amp;" in text
    assert "<b>&" not in text


def test_discount_line_disappears_without_discount() -> None:
    assert "Скидка" not in _menu(user_discount="")
    assert "10%" in _menu(user_discount="10")


def test_extra_subscriptions_line_only_when_several() -> None:
    assert "Ещё подписок" not in _menu(extra_count=0)
    assert "Ещё подписок: 2" in _menu(extra_count=2)


@pytest.fixture
def _menu_catalog():
    catalog._reset_for_tests()
    register_menu_metadata()
    yield
    catalog._reset_for_tests()


@pytest.mark.usefixtures("_menu_catalog")
async def test_menu_drops_banner_when_text_exceeds_caption(monkeypatch) -> None:
    user = MagicMock(
        id=1,
        language=Locale.EN,
        telegram_id=1,
        personal_discount=0,
        purchase_discount=0,
        loyalty_discount=0,
    )
    user.name = "Test"
    dialog_manager = MagicMock()
    dialog_manager.middleware_data = {USER_KEY: user}
    cache = MagicMock()
    cache.get_window = AsyncMock(return_value=MagicMock(banner_name="menu"))
    banner = object()

    async def _banner(*args: Any) -> object:
        return banner

    async def _buttons(*args: Any) -> list[Any]:
        return []

    getters = "app.telegram.routers.menu.getters"
    monkeypatch.setattr(f"{getters}.get_banner_media", _banner)
    monkeypatch.setattr(f"{getters}.render_dialog_buttons", _buttons)
    monkeypatch.setattr(f"{getters}.render_window_text", lambda runner, key, **kw: "x" * 1100)
    shop = MagicMock(system=AsyncMock(return_value=MagicMock(max_active_subscriptions=None)))
    referral = MagicMock(system=AsyncMock(return_value=MagicMock(enabled=False)))
    trial = AsyncMock(return_value=MagicMock(is_trial_available=False, plan=None))

    async def _call() -> dict[str, Any]:
        return await menu_getter.__dishka_orig_func__(
            dialog_manager=dialog_manager,
            config=MagicMock(),
            get_banner=MagicMock(),
            list_own_active_subscriptions=AsyncMock(return_value=[]),
            list_own_subscriptions=AsyncMock(return_value=[]),
            get_available_trial=trial,
            get_shop_settings=shop,
            get_referral_settings=referral,
            list_visible_legal_documents=MagicMock(execute=AsyncMock(return_value=[])),
            i18n=MagicMock(),
            dialog_config_cache=cache,
        )

    assert (await _call())["banner"] is None

    monkeypatch.setattr(f"{getters}.render_window_text", lambda runner, key, **kw: "x" * 100)
    assert (await _call())["banner"] is banner


def test_translated_value_rendering_only_isolation_marks_is_empty() -> None:
    # a pattern of several placeables gets bidi marks even when they all render empty
    source = seeded_fluent_source(Locale.EN, "menu.ftl").replace(
        "frg-subscription-unlimited = Unlimited", 'frg-subscription-unlimited = { "" }{ "" }'
    )
    hub = build_translator_hub([Locale.EN], {Locale.EN: source}, Locale.EN)
    runner = hub.get_translator_by_locale(Locale.EN.value)
    subscription = _subscription("ACTIVE", effective_traffic_limit=0, effective_device_limit=0)

    values = subscription_menu_values(runner, subscription, extra_count=0, trial_available=False)

    assert values["subscription_traffic_limit"] == ""
    assert values["subscription_device_limit"] == ""
    assert "Traffic limit" not in values["subscription_block"]


def test_subscription_quote_follows_its_header_without_an_invisible_line() -> None:
    runner = _runner(Locale.RU)
    values = subscription_menu_values(
        runner, _subscription("ACTIVE"), extra_count=0, trial_available=False
    )

    assert "</b>:\n<blockquote>" in values["subscription_block"]


def test_menu_shows_the_latest_expired_subscription_when_none_is_active() -> None:
    older = _subscription("EXPIRED", expire_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    newer = _subscription("EXPIRED", expire_at=datetime(2026, 10, 17, tzinfo=timezone.utc))
    active = _subscription("ACTIVE")

    assert menu_subscription(None, [older, newer]) is newer
    assert menu_subscription(active, [newer, active]) is active
    assert menu_subscription(None, []) is None
    assert "Срок действия истёк" in _menu(status="EXPIRED")
