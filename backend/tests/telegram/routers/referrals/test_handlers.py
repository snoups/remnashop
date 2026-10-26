from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from aiogram.types import CallbackQuery, Message

from app.core.constants import POINTS_WITHDRAW_RATE_LIMIT, USER_KEY
from app.core.enums import Locale
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.modules.dialogs import catalog
from app.modules.referrals import RedeemBonusDaysDto, RequestPointsWithdrawalDto
from app.telegram.dialogs import state_pool
from app.telegram.routers.menu.catalog import register_menu_catalog
from app.telegram.routers.purchase.catalog import register_purchase_catalog
from app.telegram.routers.referrals.catalog import register_referrals_catalog
from app.telegram.routers.referrals.handlers import (
    on_redeem_days,
    on_redeem_target_selected,
    on_referral_qr,
    on_withdraw_input,
    on_withdraw_points,
)
from app.telegram.routers.subscriptions.catalog import register_subscriptions_catalog
from app.telegram.states import Referrals

_LOCALES_DIR = Path(__file__).parents[4] / "assets" / "translations"


def _manager(user_bonus_days: int = 0, item_id: str = "") -> AsyncMock:
    manager = AsyncMock()
    manager.middleware_data = {
        USER_KEY: MagicMock(id=1, language=Locale.EN, bonus_days=user_bonus_days)
    }
    manager.dialog_data = {}
    manager.item_id = item_id
    return manager


def _redis(hits: int) -> MagicMock:
    pipe = MagicMock()
    pipe.execute = AsyncMock(return_value=[hits + 1, True])
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=None)
    redis = MagicMock()
    redis.pipeline.return_value = pipe
    return redis


def _i18n() -> MagicMock:
    i18n = MagicMock()
    i18n.get_translator_by_locale.return_value = MagicMock(
        get=lambda key, **kwargs: f"{key}{kwargs}" if kwargs else key
    )
    return i18n


async def test_withdraw_rejects_a_non_number() -> None:
    message = AsyncMock(text="abc")
    manager = _manager()
    use_case = AsyncMock()

    await on_withdraw_input.__dishka_orig_func__(
        message, MagicMock(), manager, use_case, _redis(0), _i18n()
    )

    use_case.assert_not_awaited()
    message.answer.assert_awaited_once_with("ntf-referrals.invalid-amount")


async def test_withdraw_rejects_a_non_positive_amount() -> None:
    message = AsyncMock(text="0")
    use_case = AsyncMock()

    await on_withdraw_input.__dishka_orig_func__(
        message, MagicMock(), _manager(), use_case, _redis(0), _i18n()
    )

    use_case.assert_not_awaited()
    message.answer.assert_awaited_once_with("ntf-referrals.invalid-amount")


async def test_withdraw_requests_the_amount_and_returns_to_the_page() -> None:
    message = AsyncMock(text=" 12,5 ")
    manager = _manager()
    use_case = AsyncMock()

    await on_withdraw_input.__dishka_orig_func__(
        message, MagicMock(), manager, use_case, _redis(0), _i18n()
    )

    assert use_case.await_args.args[1] == RequestPointsWithdrawalDto(amount=Decimal("12.5"))
    message.answer.assert_awaited_once_with("ntf-referrals.withdraw-requested")
    manager.switch_to.assert_awaited_once_with(Referrals.MAIN)


async def test_withdraw_refusal_is_reported() -> None:
    message = AsyncMock(text="100")
    use_case = AsyncMock(
        side_effect=ValidationError("too much", code=ErrorCode.WITHDRAWAL_EXCEEDS_POINTS)
    )

    await on_withdraw_input.__dishka_orig_func__(
        message, MagicMock(), _manager(), use_case, _redis(0), _i18n()
    )

    message.answer.assert_awaited_once_with("ntf-referrals.withdraw-failed")


async def test_withdraw_is_throttled() -> None:
    message = AsyncMock(text="1")
    use_case = AsyncMock()

    await on_withdraw_input.__dishka_orig_func__(
        message, MagicMock(), _manager(), use_case, _redis(POINTS_WITHDRAW_RATE_LIMIT), _i18n()
    )

    use_case.assert_not_awaited()
    message.answer.assert_awaited_once_with("ntf-referrals.too-many-attempts")


async def test_withdraw_shares_the_cabinet_rate_limit_counter() -> None:
    redis = _redis(0)

    await on_withdraw_input.__dishka_orig_func__(
        AsyncMock(text="1"), MagicMock(), _manager(), AsyncMock(), redis, _i18n()
    )

    redis.pipeline.return_value.incr.assert_called_once_with(
        "remnashop:ratelimit:points_withdraw:user:1"
    )


async def test_withdraw_points_opens_the_amount_input() -> None:
    manager = _manager()
    await on_withdraw_points(MagicMock(), MagicMock(), manager)
    manager.switch_to.assert_awaited_once_with(Referrals.WITHDRAW)


async def test_redeem_with_one_subscription_redeems_all_days() -> None:
    manager = _manager(user_bonus_days=12)
    redeem = AsyncMock()
    list_own = AsyncMock(return_value=[MagicMock(id=4)])
    callback = AsyncMock()

    await on_redeem_days.__dishka_orig_func__(
        callback, MagicMock(), manager, redeem, list_own, _i18n()
    )

    redeem.assert_awaited_once()
    assert redeem.await_args.args[1] == RedeemBonusDaysDto(subscription_id=4, days=12)
    callback.answer.assert_awaited_once_with("ntf-referrals.days-redeemed{'days': 12}")
    manager.switch_to.assert_awaited_once_with(Referrals.MAIN)


async def test_redeem_without_a_subscription_alerts() -> None:
    callback = AsyncMock()
    redeem = AsyncMock()

    await on_redeem_days.__dishka_orig_func__(
        callback,
        MagicMock(),
        _manager(user_bonus_days=3),
        redeem,
        AsyncMock(return_value=[]),
        _i18n(),
    )

    redeem.assert_not_awaited()
    callback.answer.assert_awaited_once_with("ntf-referrals.no-subscription", show_alert=True)


async def test_redeem_with_several_subscriptions_asks_for_the_target() -> None:
    manager = _manager(user_bonus_days=3)
    redeem = AsyncMock()
    list_own = AsyncMock(return_value=[MagicMock(id=4), MagicMock(id=5)])

    await on_redeem_days.__dishka_orig_func__(
        AsyncMock(), MagicMock(), manager, redeem, list_own, _i18n()
    )

    redeem.assert_not_awaited()
    manager.switch_to.assert_awaited_once_with(Referrals.REDEEM_TARGET)


async def test_redeem_into_the_chosen_subscription() -> None:
    manager = _manager(user_bonus_days=7, item_id="5")
    redeem = AsyncMock()

    await on_redeem_target_selected.__dishka_orig_func__(
        AsyncMock(), MagicMock(), manager, redeem, _i18n()
    )

    assert redeem.await_args.args[1] == RedeemBonusDaysDto(subscription_id=5, days=7)
    manager.switch_to.assert_awaited_once_with(Referrals.MAIN)


async def test_redeem_refusal_is_reported() -> None:
    callback = AsyncMock()
    redeem = AsyncMock(
        side_effect=ValidationError("trial", code=ErrorCode.BONUS_DAYS_TRIAL_SUBSCRIPTION)
    )

    await on_redeem_days.__dishka_orig_func__(
        callback,
        MagicMock(),
        _manager(user_bonus_days=3),
        redeem,
        AsyncMock(return_value=[MagicMock(id=4)]),
        _i18n(),
    )

    callback.answer.assert_awaited_once_with("ntf-referrals.redeem-failed", show_alert=True)


def test_every_referral_notification_exists_in_each_locale() -> None:
    attributes = (
        "invalid-amount",
        "too-many-attempts",
        "withdraw-failed",
        "withdraw-requested",
        "no-subscription",
        "days-redeemed",
        "redeem-failed",
    )
    for menu in _LOCALES_DIR.glob("*/menu.ftl"):
        text = menu.read_text()
        section = text.split("ntf-referrals =", 1)[1].split("\n\n", 1)[0]
        assert all(f"    .{attribute} =" in section for attribute in attributes), menu


def test_every_catalog_action_has_a_bound_handler() -> None:
    catalog._reset_for_tests()
    state_pool._reset_for_tests()
    try:
        register_menu_catalog()
        register_subscriptions_catalog()
        register_purchase_catalog()
        register_referrals_catalog()
        assert {
            key for key in catalog.action_keys() if not catalog.has_action_handler(key)
        } == set()
    finally:
        catalog._reset_for_tests()
        state_pool._reset_for_tests()


async def test_qr_sends_the_referral_link_as_a_png() -> None:
    callback = MagicMock(spec=CallbackQuery)
    callback.message = MagicMock(spec=Message)
    callback.message.answer_photo = AsyncMock()
    callback.answer = AsyncMock()
    bot = MagicMock(me=AsyncMock(return_value=MagicMock(username="shop_bot")))

    await on_referral_qr.__dishka_orig_func__(
        callback,
        MagicMock(),
        _manager(),
        AsyncMock(return_value=MagicMock(referral_code="abc")),
        bot,
    )

    photo = callback.message.answer_photo.await_args.args[0]
    assert photo.data.startswith(b"\x89PNG")
    callback.answer.assert_awaited_once()
