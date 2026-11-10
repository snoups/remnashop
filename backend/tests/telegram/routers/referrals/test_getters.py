import html
from decimal import Decimal
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.constants import USER_KEY
from app.core.enums import (
    Locale,
    ReferralAccrualStrategy,
    ReferralRewardStrategy,
    ReferralRewardType,
)
from app.core.error_codes import ErrorCode
from app.core.utils.telegram_text import validate_telegram_html
from app.modules.dialogs import catalog, register_all_flow_metadata
from app.modules.referrals import ReferralSettingsDto
from app.telegram.dialogs.rendering import render_window_text
from app.telegram.i18n import build_translator_hub
from app.telegram.routers.referrals.getters import (
    referral_url,
    referrals_getter,
    reward_about_values,
)
from tests.seeded_translations import seeded_fluent_source


@pytest.fixture(autouse=True)
def _catalog():
    catalog._reset_for_tests()
    register_all_flow_metadata()
    yield
    catalog._reset_for_tests()


def test_referral_url() -> None:
    assert referral_url("shop_bot", "ABC") == "https://t.me/shop_bot?start=ref_ABC"


def _system(value: MagicMock) -> MagicMock:
    usecase = MagicMock()
    usecase.system = AsyncMock(return_value=value)
    return usecase


async def _render(
    code: Optional[str], points: Decimal, bonus_days: int, i18n: Optional[object] = None
) -> dict:
    user = MagicMock(
        id=1,
        telegram_id=42,
        points=points,
        bonus_days=bonus_days,
        language=Locale.EN,
        personal_discount=0,
        purchase_discount=0,
        loyalty_discount=0,
    )
    manager = MagicMock()
    manager.middleware_data = {USER_KEY: user}
    stats = MagicMock(
        referral_code=code, points=points, bonus_days=bonus_days, counts_by_level={1: 3}
    )
    if i18n is None:
        i18n = MagicMock()
        i18n.get_translator_by_locale.return_value = MagicMock(get=lambda key, **kwargs: key)
    cache = MagicMock()
    cache.get_window = AsyncMock(return_value=MagicMock(banner_name=None, buttons=[]))
    bot = MagicMock()
    bot.me = AsyncMock(return_value=MagicMock(username="shop_bot"))

    return await referrals_getter.__dishka_orig_func__(
        manager,
        config=MagicMock(),
        get_banner=AsyncMock(),
        list_own_active_subscriptions=AsyncMock(return_value=[]),
        list_own_subscriptions=AsyncMock(return_value=[]),
        get_available_trial=AsyncMock(return_value=MagicMock(is_trial_available=False)),
        get_shop_settings=_system(MagicMock(max_active_subscriptions=None)),
        get_referral_settings=_system(MagicMock(enabled=True)),
        get_own_referral_stats=AsyncMock(return_value=stats),
        bot=bot,
        i18n=i18n,
        dialog_config_cache=cache,
    )


async def test_getter_builds_the_link_and_flags() -> None:
    data = await _render("ABC", Decimal("5"), 0)

    assert data["referral_url"] == "https://t.me/shop_bot?start=ref_ABC"
    assert data["has_points"] is True
    assert data["has_bonus_days"] is False
    assert data["window_text"] == "msg-referrals"


async def test_getter_without_a_code_has_no_link() -> None:
    data = await _render(None, Decimal("0"), 2)

    assert data["referral_url"] == ""
    assert data["has_points"] is False
    assert data["has_bonus_days"] is True


async def test_window_text_drops_zero_stats() -> None:
    hub = build_translator_hub(
        [Locale.EN], {Locale.EN: seeded_fluent_source(Locale.EN, "menu.ftl")}, Locale.EN
    )

    text = (await _render("ABC", Decimal("0"), 0, i18n=hub))["window_text"]

    assert "<b>Invited by you</b>: 3" in text
    assert "Invited by your friends" not in text
    assert "Points" not in text
    assert "Bonus days" not in text
    assert text.endswith("</blockquote>")

    text = (await _render("ABC", Decimal("5"), 2, i18n=hub))["window_text"]
    assert "<b>Points</b>: 5" in text
    assert "<b>Bonus days</b>: 2" in text


def _about(locale: Locale, **settings: Any) -> str:
    hub = build_translator_hub([locale], {locale: seeded_fluent_source(locale, "menu.ftl")}, locale)
    runner = hub.get_translator_by_locale(locale.value)
    values = reward_about_values(runner, ReferralSettingsDto(**settings))
    return render_window_text(runner, "msg-referrals-about", **values)


def test_about_describes_the_program_terms() -> None:
    text = _about(
        Locale.RU,
        max_level=2,
        reward_type=ReferralRewardType.EXTRA_DAYS,
        reward_strategy=ReferralRewardStrategy.AMOUNT,
        reward_amounts={1: Decimal("5"), 2: Decimal("2")},
        accrual_strategy=ReferralAccrualStrategy.EVERY_PAYMENT,
        invitee_reward_type=ReferralRewardType.EXTRA_DAYS,
        invitee_reward_amount=3,
    )

    assert "Вы получаете +5 дней за оплату друга. За каждую его оплату" in text
    assert "И сразу получает +3 бонусных дня." in text
    assert "Друзья ваших друзей тоже приносят награду:\n2 уровень — +2 дня за оплату друга" in text
    assert "Применяйте бонусные дни" in text
    validate_telegram_html(text, code=ErrorCode.TRANSLATION_HTML_INVALID)


def test_about_without_invitee_gift_or_deeper_levels() -> None:
    text = _about(
        Locale.EN,
        max_level=1,
        reward_type=ReferralRewardType.POINTS,
        reward_strategy=ReferralRewardStrategy.PERCENT,
        reward_amounts={1: Decimal("12.50")},
    )

    shown = html.unescape(text)
    assert "You get 12.5% of a friend's payment as points. For their first payment only." in shown
    assert "And becomes your referral." in text
    assert "Friends of your friends" not in text
    assert "Exchange your points" in text
    validate_telegram_html(text, code=ErrorCode.TRANSLATION_HTML_INVALID)
