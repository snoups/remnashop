from aiogram import Router

from app.telegram.routers.promocode.dialog import router as promocode_dialog_router
from app.telegram.states import Subscription


def test_promocode_dialog_router_builds() -> None:
    parent = Router(name="test-parent")
    parent.include_router(promocode_dialog_router)
    assert promocode_dialog_router is not None


def test_promocode_dialog_includes_promocode_input_window() -> None:
    states = {window.state for window in promocode_dialog_router.windows.values()}
    assert Subscription.PROMOCODE in states


def test_promocode_dialog_includes_promocode_target_window() -> None:
    states = {window.state for window in promocode_dialog_router.windows.values()}
    assert Subscription.PROMOCODE_TARGET in states


def test_promocode_dialog_includes_promocode_confirm_window() -> None:
    states = {window.state for window in promocode_dialog_router.windows.values()}
    assert Subscription.PROMOCODE_CONFIRM in states
