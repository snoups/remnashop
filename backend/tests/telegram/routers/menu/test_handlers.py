from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from aiogram_dialog import StartMode

from app.core.constants import USER_KEY
from app.core.enums import Currency, PurchaseType
from app.modules.subscriptions.dto import GetAvailableTrialDto
from app.telegram.dialogs.context import SELECTED_SUBSCRIPTION_KEY
from app.telegram.routers.menu.handlers import on_get_trial
from app.telegram.routers.purchase.handlers import PLAN_CODE_KEY
from app.telegram.states import Purchase, Subscriptions


def _manager() -> MagicMock:
    manager = MagicMock()
    manager.middleware_data = {USER_KEY: MagicMock(id=1)}
    manager.start = AsyncMock()
    manager.switch_to = AsyncMock()
    return manager


def _trial(price: Decimal) -> GetAvailableTrialDto:
    return GetAvailableTrialDto(
        plan=MagicMock(public_code="trialCode"),
        is_trial_available=True,
        price=price,
        currency=Currency.USD,
    )


async def test_a_free_trial_is_activated_on_the_spot() -> None:
    manager = _manager()
    activate = AsyncMock(return_value=MagicMock(id=7))

    await on_get_trial.__dishka_orig_func__(
        MagicMock(answer=AsyncMock()),
        MagicMock(),
        manager,
        get_available_trial=AsyncMock(return_value=_trial(Decimal(0))),
        activate_trial_subscription=activate,
        i18n=MagicMock(),
    )

    activate.assert_awaited_once()
    # the card holds "Connect", which the menu lacks when several subscriptions are allowed
    manager.start.assert_awaited_once_with(
        Subscriptions.CARD, data={SELECTED_SUBSCRIPTION_KEY: 7}, mode=StartMode.RESET_STACK
    )


async def test_a_paid_trial_opens_its_purchase() -> None:
    manager = _manager()
    activate = AsyncMock()

    await on_get_trial.__dishka_orig_func__(
        MagicMock(answer=AsyncMock()),
        MagicMock(),
        manager,
        get_available_trial=AsyncMock(return_value=_trial(Decimal("1.5"))),
        activate_trial_subscription=activate,
        i18n=MagicMock(),
    )

    activate.assert_not_awaited()
    manager.start.assert_awaited_once_with(
        Purchase.PLAN,
        data={"purchase_type": PurchaseType.NEW.value, PLAN_CODE_KEY: "trialCode"},
    )
