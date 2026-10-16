from aiogram import Router

from app.telegram.routers.purchase.dialog import router
from app.telegram.states import Purchase


def test_purchase_dialog_builds_with_every_step() -> None:
    Router(name="test-parent").include_router(router)
    assert {window.state for window in router.windows.values()} == set(Purchase.__states__)
