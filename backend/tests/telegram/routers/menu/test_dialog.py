from aiogram import Router

from app.telegram.routers.menu.dialog import router as menu_dialog_router
from app.telegram.states import MainMenu


def test_menu_dialog_router_builds() -> None:
    parent = Router(name="test-parent")
    parent.include_router(menu_dialog_router)
    assert menu_dialog_router is not None


def test_menu_dialog_includes_devices_window() -> None:
    states = {window.state for window in menu_dialog_router.windows.values()}
    assert MainMenu.DEVICES in states


def test_menu_dialog_includes_device_confirm_windows() -> None:
    states = {window.state for window in menu_dialog_router.windows.values()}
    assert MainMenu.DEVICE_CONFIRM_DELETE in states
    assert MainMenu.DEVICE_CONFIRM_DELETE_ALL in states
    assert MainMenu.DEVICE_CONFIRM_REISSUE in states
