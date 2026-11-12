from typing import Any
from unittest.mock import AsyncMock, MagicMock

from aiogram import Dispatcher
from aiogram.dispatcher.event.telegram import TelegramEventObserver
from aiogram.types import User as AiogramUser
from aiogram_dialog import StartMode

from app.core.constants import CONTAINER_KEY, USER_KEY
from app.core.enums import Locale, PurchaseType
from app.telegram.middlewares import setup_middlewares
from app.telegram.routers.payment_result.getters import (
    canceled_getter,
    failed_getter,
    success_getter,
)
from app.telegram.routers.payment_result.handlers import on_open_subscription, on_retry
from app.telegram.states import Purchase, Subscriptions


def _get(key: str, **kwargs: Any) -> str:
    return f"{key}{kwargs}" if kwargs else key


def _i18n() -> MagicMock:
    i18n = MagicMock()
    i18n.get_translator_by_locale.return_value = MagicMock(get=_get)
    return i18n


def _manager() -> MagicMock:
    manager = MagicMock()
    manager.middleware_data = {USER_KEY: MagicMock(id=1, language=Locale.EN)}
    manager.start_data = {"order_id": 7}
    manager.start = AsyncMock()
    return manager


def _order(**overrides: Any) -> MagicMock:
    values: dict[str, Any] = {
        "purchase_type": PurchaseType.RENEW,
        "plan_snapshot": MagicMock(),
        "plan_id": 10,
        "duration_days": 30,
        "target_subscription_id": 3,
        "fulfilled_subscription_id": 3,
    }
    values.update(overrides)
    order = MagicMock(**values)
    order.plan_snapshot.name = "Pro"
    return order


async def test_success_getter_renders_the_order() -> None:
    data = await success_getter.__dishka_orig_func__(
        _manager(),
        get_own_transaction=AsyncMock(return_value=_order()),
        list_own_subscriptions=AsyncMock(return_value=[]),
        i18n=_i18n(),
    )

    assert "Pro" in data["window_text"]
    assert "RENEW" in data["window_text"]
    assert data["has_subscription"] is True


async def test_success_getter_hides_the_subscription_button_without_one() -> None:
    order = _order(fulfilled_subscription_id=None)

    data = await success_getter.__dishka_orig_func__(
        _manager(),
        get_own_transaction=AsyncMock(return_value=order),
        list_own_subscriptions=AsyncMock(return_value=[]),
        i18n=_i18n(),
    )

    assert data["has_subscription"] is False


async def test_a_new_subscription_is_connected_from_the_success_window() -> None:
    order = _order(purchase_type=PurchaseType.NEW)
    subscription = MagicMock(id=order.fulfilled_subscription_id, url="https://sub.example/x")

    data = await success_getter.__dishka_orig_func__(
        _manager(),
        get_own_transaction=AsyncMock(return_value=order),
        list_own_subscriptions=AsyncMock(return_value=[subscription]),
        i18n=_i18n(),
    )

    assert data["connect_url"] == "https://sub.example/x"


async def test_failed_getter_has_text_and_menu() -> None:
    data = await failed_getter.__dishka_orig_func__(_manager(), i18n=_i18n())

    assert data["window_text"] == "msg-payment-result-failed"
    assert "menu_text" in data


async def test_canceled_getter_offers_retry() -> None:
    data = await canceled_getter.__dishka_orig_func__(_manager(), i18n=_i18n())

    assert data["window_text"] == "msg-payment-result-canceled"
    assert {"retry_text", "menu_text"} <= data.keys()


async def test_retry_restarts_the_purchase_from_the_order() -> None:
    manager = _manager()

    await on_retry.__dishka_orig_func__(
        MagicMock(), MagicMock(), manager, get_own_transaction=AsyncMock(return_value=_order())
    )

    manager.start.assert_awaited_once_with(
        Purchase.PLAN,
        data={
            "purchase_type": "RENEW",
            "subscription_id": 3,
            "retry_plan_id": 10,
            "retry_duration_days": 30,
        },
        mode=StartMode.RESET_STACK,
    )


async def test_open_subscription_starts_the_card() -> None:
    manager = _manager()

    await on_open_subscription.__dishka_orig_func__(
        MagicMock(), MagicMock(), manager, get_own_transaction=AsyncMock(return_value=_order())
    )

    manager.start.assert_awaited_once_with(
        Subscriptions.CARD, data={"subscription_id": 3}, mode=StartMode.RESET_STACK
    )


class _Container:
    def __init__(self, user: object) -> None:
        self._user = user

    async def get(self, dependency_type: type) -> Any:
        return MagicMock(system=AsyncMock(return_value=self._user))


async def test_dialog_updates_get_the_user() -> None:
    dispatcher = Dispatcher()
    dispatcher.observers["aiogd_update"] = TelegramEventObserver(
        router=dispatcher, event_name="aiogd_update"
    )
    setup_middlewares(dispatcher)
    seen: dict[str, Any] = {}

    async def handler(event: object, **data: Any) -> None:
        seen.update(data)

    dispatcher.observers["aiogd_update"].register(handler)
    user = MagicMock()

    await dispatcher.propagate_event(
        "aiogd_update",
        object(),
        event_from_user=AiogramUser(id=5, is_bot=False, first_name=""),
        **{CONTAINER_KEY: _Container(user)},
    )

    assert seen[USER_KEY] is user
