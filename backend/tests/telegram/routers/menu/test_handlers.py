from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram_dialog import StartMode
from remnapy.enums import TrafficLimitStrategy

from app.core.constants import USER_KEY
from app.core.enums import Currency, PurchaseType, SubscriptionStatus
from app.modules.subscriptions.dto import GetAvailableTrialDto
from app.telegram.dialogs.context import SELECTED_SUBSCRIPTION_KEY
from app.telegram.routers.menu.handlers import (
    next_traffic_reset,
    on_get_trial,
    on_show_connect_problem,
)
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


_NOW = datetime(2026, 11, 12, 15, 30, tzinfo=timezone.utc)  # a Thursday


@pytest.mark.parametrize(
    ("strategy", "created", "expected"),
    [
        (TrafficLimitStrategy.NO_RESET, None, None),
        (TrafficLimitStrategy.DAY, None, datetime(2026, 11, 13, tzinfo=timezone.utc)),
        (TrafficLimitStrategy.WEEK, None, datetime(2026, 11, 16, tzinfo=timezone.utc)),
        (TrafficLimitStrategy.MONTH, None, datetime(2026, 12, 1, tzinfo=timezone.utc)),
        (
            TrafficLimitStrategy.MONTH_ROLLING,
            datetime(2026, 1, 20, tzinfo=timezone.utc),
            datetime(2026, 11, 20, tzinfo=timezone.utc),
        ),
        (
            TrafficLimitStrategy.MONTH_ROLLING,
            datetime(2026, 1, 5, tzinfo=timezone.utc),
            datetime(2026, 12, 5, tzinfo=timezone.utc),
        ),
        # the 31st in a 30-day month falls on its last day
        (
            TrafficLimitStrategy.MONTH_ROLLING,
            datetime(2026, 1, 31, tzinfo=timezone.utc),
            datetime(2026, 11, 30, tzinfo=timezone.utc),
        ),
    ],
)
def test_next_traffic_reset(
    strategy: TrafficLimitStrategy, created: object, expected: object
) -> None:
    assert next_traffic_reset(strategy, created, _NOW) == expected  # type: ignore[arg-type]


def _subscription(status: SubscriptionStatus, *, is_trial: bool = False) -> MagicMock:
    return MagicMock(
        status=status,
        is_trial=is_trial,
        traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
        created_at=_NOW,
    )


async def _show(subscription: MagicMock, manager: MagicMock) -> MagicMock:
    callback = MagicMock(answer=AsyncMock())
    runner = MagicMock(get=lambda key, **kwargs: f"{key}{sorted(kwargs.items())}")
    await on_show_connect_problem.__dishka_orig_func__(
        callback,
        MagicMock(),
        manager,
        list_own_active_subscriptions=AsyncMock(return_value=[subscription]),
        list_own_subscriptions=AsyncMock(return_value=[subscription]),
        i18n=MagicMock(get_translator_by_locale=MagicMock(return_value=runner)),
    )
    return callback


async def test_the_warning_explains_itself_in_an_alert() -> None:
    callback = await _show(_subscription(SubscriptionStatus.EXPIRED, is_trial=True), _manager())

    callback.answer.assert_awaited_once_with(
        "ntf-common.connect-not-available"
        "[('is_trial', 1), ('reset_in', 'none'), ('status', 'EXPIRED')]",
        show_alert=True,
    )


async def test_a_warning_left_after_the_fix_just_redraws_the_menu() -> None:
    manager = _manager()
    manager.show = AsyncMock()

    callback = await _show(_subscription(SubscriptionStatus.ACTIVE), manager)

    callback.answer.assert_not_awaited()
    manager.show.assert_awaited_once()
