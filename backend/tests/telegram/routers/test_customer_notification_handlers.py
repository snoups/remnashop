from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import CallbackQuery

from app.core.enums import PurchaseType
from app.modules.users import UserDto
from app.telegram.dialogs.context import SELECTED_SUBSCRIPTION_KEY
from app.telegram.routers.customer_notifications.handlers import on_notification_renew
from app.telegram.states import Purchase


async def _press(data: str, subscriptions: list[Any]) -> dict[str, Any]:
    callback = MagicMock(spec=CallbackQuery)
    callback.data = data
    callback.answer = AsyncMock()
    dialog_manager = MagicMock(start=AsyncMock())
    await on_notification_renew(
        callback,
        UserDto(id=1, name="c", telegram_id=5),
        dialog_manager,
        AsyncMock(return_value=subscriptions),
    )
    state, *_ = dialog_manager.start.await_args.args
    assert state == Purchase.PLAN
    return dialog_manager.start.await_args.kwargs["data"]


@pytest.mark.parametrize(
    ("is_trial", "subscription_id", "renews"),
    [(False, 7, True), (True, 7, False), (False, 8, False)],
)
async def test_renew_button_renews_only_an_owned_paid_subscription(
    is_trial: bool, subscription_id: int, renews: bool
) -> None:
    data = await _press(f"cn:renew:{subscription_id}", [MagicMock(id=7, is_trial=is_trial)])

    expected: dict[str, Optional[Any]] = (
        {"purchase_type": PurchaseType.RENEW.value, SELECTED_SUBSCRIPTION_KEY: 7}
        if renews
        else {"purchase_type": PurchaseType.NEW.value}
    )
    assert data == expected
