from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram_dialog import StartMode
from dishka.integrations.aiogram_dialog import CONTAINER_NAME

from app.core.constants import USER_KEY
from app.core.enums import Locale
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, ValidationError
from app.telegram.dialogs.context import SELECTED_SUBSCRIPTION_KEY
from app.telegram.routers.subscriptions.handlers import (
    DEVICES_FROM_MENU_KEY,
    on_device_delete_confirm,
    on_devices_back,
    on_reissue_subscription_confirm,
    on_subscription_card_back,
    on_subscription_selected,
    open_subscriptions,
)
from app.telegram.states import MainMenu, Subscriptions

_LOCALES_DIR = Path(__file__).parents[4] / "assets" / "translations"


def _container(max_active: object) -> MagicMock:
    get_shop_settings = MagicMock(
        system=AsyncMock(return_value=MagicMock(max_active_subscriptions=max_active))
    )
    return MagicMock(get=AsyncMock(return_value=get_shop_settings))


def _manager(dialog_data: dict, start_data: object = None, max_active: object = 1) -> AsyncMock:
    manager = AsyncMock()
    manager.middleware_data = {
        USER_KEY: MagicMock(id=1, language=Locale.EN),
        CONTAINER_NAME: _container(max_active),
    }
    manager.dialog_data = dialog_data
    manager.start_data = start_data
    return manager


def _i18n() -> MagicMock:
    i18n = MagicMock()
    i18n.get_translator_by_locale.return_value = MagicMock(get=lambda key, **kwargs: key)
    return i18n


async def test_open_subscriptions_with_the_only_one_allowed_goes_straight_to_the_card() -> None:
    manager = _manager({})
    await open_subscriptions(manager, [MagicMock(id=7)])
    manager.start.assert_awaited_once_with(
        Subscriptions.CARD, data={SELECTED_SUBSCRIPTION_KEY: 7}, mode=StartMode.RESET_STACK
    )


@pytest.mark.parametrize("max_active", [3, None])
async def test_open_subscriptions_with_room_for_more_shows_the_list(max_active: object) -> None:
    # buying one more starts from the list, so one subscription doesn't skip it
    manager = _manager({}, max_active=max_active)
    await open_subscriptions(manager, [MagicMock(id=7)])
    manager.start.assert_awaited_once_with(Subscriptions.LIST, mode=StartMode.RESET_STACK)


async def test_card_back_with_room_for_more_returns_to_the_list() -> None:
    manager = _manager({}, max_active=3)
    list_own = AsyncMock(return_value=[MagicMock(id=7)])

    await on_subscription_card_back.__dishka_orig_func__(
        MagicMock(), MagicMock(), manager, list_own_subscriptions=list_own
    )

    manager.start.assert_awaited_once_with(Subscriptions.LIST, mode=StartMode.RESET_STACK)


async def test_devices_opened_from_the_menu_go_back_to_it() -> None:
    manager = _manager({}, start_data={DEVICES_FROM_MENU_KEY: True})
    await on_devices_back(MagicMock(), MagicMock(), manager)
    manager.start.assert_awaited_once_with(MainMenu.MAIN, mode=StartMode.RESET_STACK)


async def test_devices_opened_from_a_card_go_back_to_it() -> None:
    manager = _manager({}, start_data={SELECTED_SUBSCRIPTION_KEY: 7})
    await on_devices_back(MagicMock(), MagicMock(), manager)
    manager.switch_to.assert_awaited_once_with(Subscriptions.CARD)


async def test_open_subscriptions_with_several_shows_the_list() -> None:
    manager = AsyncMock()
    await open_subscriptions(manager, [MagicMock(id=7), MagicMock(id=8)])
    manager.start.assert_awaited_once_with(Subscriptions.LIST, mode=StartMode.RESET_STACK)


async def test_open_subscriptions_with_none_returns_to_the_menu() -> None:
    manager = AsyncMock()
    await open_subscriptions(manager, [])
    manager.start.assert_awaited_once_with(MainMenu.MAIN, mode=StartMode.RESET_STACK)


async def test_card_back_with_one_subscription_returns_to_the_menu() -> None:
    manager = _manager({})
    list_own = AsyncMock(return_value=[MagicMock(id=7)])

    await on_subscription_card_back.__dishka_orig_func__(
        MagicMock(), MagicMock(), manager, list_own_subscriptions=list_own
    )

    manager.start.assert_awaited_once_with(MainMenu.MAIN, mode=StartMode.RESET_STACK)


async def test_card_back_with_several_subscriptions_returns_to_the_list() -> None:
    manager = _manager({})
    list_own = AsyncMock(return_value=[MagicMock(id=7), MagicMock(id=8)])

    await on_subscription_card_back.__dishka_orig_func__(
        MagicMock(), MagicMock(), manager, list_own_subscriptions=list_own
    )

    manager.start.assert_awaited_once_with(Subscriptions.LIST, mode=StartMode.RESET_STACK)


async def test_selecting_a_subscription_opens_its_card() -> None:
    manager = _manager({})
    manager.item_id = "8"

    await on_subscription_selected(MagicMock(), MagicMock(), manager)

    assert manager.dialog_data[SELECTED_SUBSCRIPTION_KEY] == 8
    manager.switch_to.assert_awaited_once_with(Subscriptions.CARD)


async def test_device_delete_targets_the_selected_subscription() -> None:
    manager = _manager({"selected_hwid": "hw"}, start_data={SELECTED_SUBSCRIPTION_KEY: 7})
    delete_device = AsyncMock()

    await on_device_delete_confirm.__dishka_orig_func__(
        AsyncMock(),
        MagicMock(),
        manager,
        delete_device=delete_device,
        list_own_subscriptions=AsyncMock(),
        i18n=_i18n(),
    )

    data = delete_device.await_args.args[1]
    assert (data.subscription_id, data.hwid) == (7, "hw")
    manager.switch_to.assert_awaited_once_with(state=Subscriptions.DEVICES)


async def test_device_delete_on_a_gone_subscription_reopens_the_subscriptions() -> None:
    manager = _manager({"selected_hwid": "hw", SELECTED_SUBSCRIPTION_KEY: 7})
    callback = AsyncMock()
    delete_device = AsyncMock(
        side_effect=NotFoundError("gone", code=ErrorCode.SUBSCRIPTION_NOT_FOUND)
    )

    await on_device_delete_confirm.__dishka_orig_func__(
        callback,
        MagicMock(),
        manager,
        delete_device=delete_device,
        list_own_subscriptions=AsyncMock(return_value=[]),
        i18n=_i18n(),
    )

    callback.answer.assert_awaited_once_with("ntf-subscription.gone", show_alert=True)
    manager.start.assert_awaited_once_with(MainMenu.MAIN, mode=StartMode.RESET_STACK)


async def test_device_delete_without_a_selected_subscription_reopens_the_subscriptions() -> None:
    manager = _manager({"selected_hwid": "hw"})
    callback = AsyncMock()
    delete_device = AsyncMock()

    await on_device_delete_confirm.__dishka_orig_func__(
        callback,
        MagicMock(),
        manager,
        delete_device=delete_device,
        list_own_subscriptions=AsyncMock(return_value=[MagicMock(id=7), MagicMock(id=8)]),
        i18n=_i18n(),
    )

    delete_device.assert_not_awaited()
    callback.answer.assert_awaited_once_with("ntf-subscription.gone", show_alert=True)
    manager.start.assert_awaited_once_with(Subscriptions.LIST, mode=StartMode.RESET_STACK)


@pytest.mark.parametrize(
    "code", [ErrorCode.SUBSCRIPTION_DELETED, ErrorCode.TARGET_SUBSCRIPTION_NOT_OWNED]
)
async def test_device_delete_on_a_deleted_or_foreign_subscription_reopens_the_subscriptions(
    code: ErrorCode,
) -> None:
    manager = _manager({"selected_hwid": "hw", SELECTED_SUBSCRIPTION_KEY: 7})
    callback = AsyncMock()

    await on_device_delete_confirm.__dishka_orig_func__(
        callback,
        MagicMock(),
        manager,
        delete_device=AsyncMock(side_effect=ValidationError("gone", code=code)),
        list_own_subscriptions=AsyncMock(return_value=[]),
        i18n=_i18n(),
    )

    callback.answer.assert_awaited_once_with("ntf-subscription.gone", show_alert=True)
    manager.start.assert_awaited_once_with(MainMenu.MAIN, mode=StartMode.RESET_STACK)


async def test_device_delete_turned_off_by_the_admin_stays_in_the_window() -> None:
    manager = _manager({"selected_hwid": "hw", SELECTED_SUBSCRIPTION_KEY: 7})
    callback = AsyncMock()
    error = ValidationError("off", code=ErrorCode.DEVICE_RESET_DISABLED)

    await on_device_delete_confirm.__dishka_orig_func__(
        callback,
        MagicMock(),
        manager,
        delete_device=AsyncMock(side_effect=error),
        list_own_subscriptions=AsyncMock(),
        i18n=_i18n(),
    )

    callback.answer.assert_awaited_once_with("ntf-devices.reset-disabled", show_alert=True)
    manager.start.assert_not_awaited()
    manager.switch_to.assert_not_awaited()


async def test_reissue_turned_off_by_the_admin_stays_in_the_window() -> None:
    manager = _manager({SELECTED_SUBSCRIPTION_KEY: 7})
    callback = AsyncMock()
    error = ValidationError("off", code=ErrorCode.LINK_RESET_DISABLED)

    await on_reissue_subscription_confirm.__dishka_orig_func__(
        callback,
        MagicMock(),
        manager,
        reissue_subscription=AsyncMock(side_effect=error),
        list_own_subscriptions=AsyncMock(),
        i18n=_i18n(),
    )

    callback.answer.assert_awaited_once_with("ntf-devices.reset-disabled", show_alert=True)
    manager.start.assert_not_awaited()


async def test_device_delete_other_refusal_answers_generically_and_stays() -> None:
    manager = _manager({"selected_hwid": "hw", SELECTED_SUBSCRIPTION_KEY: 7})
    callback = AsyncMock()
    error = ValidationError("other", code=ErrorCode.SUBSCRIPTION_DISABLED)

    await on_device_delete_confirm.__dishka_orig_func__(
        callback,
        MagicMock(),
        manager,
        delete_device=AsyncMock(side_effect=error),
        list_own_subscriptions=AsyncMock(),
        i18n=_i18n(),
    )

    callback.answer.assert_awaited_once_with("ntf-devices.failed", show_alert=True)
    manager.start.assert_not_awaited()


def test_gone_notification_exists_in_each_locale() -> None:
    for menu in _LOCALES_DIR.glob("*/menu.ftl"):
        text = menu.read_text()
        assert "ntf-subscription =\n    .gone =" in text, menu
        assert "    .reset-disabled =" in text, menu
        assert "    .failed =" in text, menu
