from decimal import Decimal
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.constants import USER_KEY
from app.core.enums import Locale
from app.modules.dialogs import catalog, register_all_flow_metadata
from app.telegram.routers.referrals.getters import referral_url, referrals_getter


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


async def _render(code: Optional[str], points: Decimal, bonus_days: int) -> dict:
    user = MagicMock(id=1, telegram_id=42, points=points, bonus_days=bonus_days, language=Locale.EN)
    manager = MagicMock()
    manager.middleware_data = {USER_KEY: user}
    stats = MagicMock(
        referral_code=code, points=points, bonus_days=bonus_days, counts_by_level={1: 3}
    )
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
