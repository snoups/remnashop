from aiogram import Router

from app.telegram.routers.menu.dialog import router as menu_dialog_router
from app.telegram.routers.subscriptions.dialog import router as subscriptions_dialog_router
from app.telegram.states import MainMenu, Subscriptions


def test_dialog_routers_build() -> None:
    parent = Router(name="test-parent")
    parent.include_router(menu_dialog_router)
    parent.include_router(subscriptions_dialog_router)


def test_menu_dialog_keeps_only_the_main_window() -> None:
    states = {window.state for window in menu_dialog_router.windows.values()}
    assert states == {MainMenu.MAIN}


def test_subscriptions_dialog_includes_list_card_and_device_windows() -> None:
    states = {window.state for window in subscriptions_dialog_router.windows.values()}
    assert states == {
        Subscriptions.LIST,
        Subscriptions.CARD,
        Subscriptions.DEVICES,
        Subscriptions.DEVICE_CONFIRM_DELETE,
        Subscriptions.DEVICE_CONFIRM_DELETE_ALL,
        Subscriptions.DEVICE_CONFIRM_REISSUE,
    }
