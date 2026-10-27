from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Message
from aiogram_dialog import StartMode

from app.core.constants import USER_KEY
from app.core.enums import Currency, PurchaseType
from app.modules.subscriptions import ListActivePlansDto, PlanCatalogDto
from app.modules.transactions.dto import CheckoutResultDto
from app.telegram.dialogs.context import SELECTED_SUBSCRIPTION_KEY
from app.telegram.routers.purchase.deeplink import on_plan_link
from app.telegram.routers.purchase.getters import duration_getter, link_choice_getter
from app.telegram.routers.purchase.handlers import (
    LINK_CHOICE_KEY,
    PLAN_CODE_KEY,
    on_confirm,
    on_duration_back,
    on_link_new,
    on_link_renew,
    on_purchase_start,
    start_purchase_steps,
)
from app.telegram.states import MainMenu, Purchase
from tests.telegram.routers.purchase.test_getters import _get
from tests.telegram.routers.purchase.test_getters import _i18n as _getter_i18n
from tests.telegram.routers.purchase.test_getters import _manager as _getter_manager
from tests.telegram.routers.purchase.test_handlers import (
    _confirm_data,
    _i18n,
    _manager,
    _plan,
)

_LINK_START = {"purchase_type": "NEW", PLAN_CODE_KEY: "Ab12Cd34"}


def _catalog(*ids: int) -> PlanCatalogDto:
    return PlanCatalogDto(plans=[_plan(id=i) for i in ids], anchor_currency=Currency.RUB)


def _subscription(id: int, plan_id: int) -> Any:
    snapshot = MagicMock(plan_id=plan_id)
    snapshot.name = f"Plan {plan_id}"
    return MagicMock(
        id=id, plan_snapshot=snapshot, expire_at=datetime(2026, 11, 1, tzinfo=timezone.utc)
    )


async def test_plan_link_starts_the_purchase_with_its_code() -> None:
    manager = AsyncMock()
    command = MagicMock(args="plan_Ab12Cd34")

    await on_plan_link(MagicMock(), command, manager)

    manager.start.assert_awaited_once_with(
        Purchase.PLAN, data=_LINK_START, mode=StartMode.RESET_STACK
    )


async def test_link_without_a_subscription_on_the_plan_opens_the_durations() -> None:
    manager = _manager(start_data=_LINK_START)

    key = await start_purchase_steps(manager, _catalog(10), [_subscription(3, plan_id=99)])

    assert key is None
    assert manager.dialog_data["plan_id"] == 10
    assert manager.dialog_data[PLAN_CODE_KEY] == "Ab12Cd34"
    manager.switch_to.assert_awaited_once_with(Purchase.DURATION)


async def test_link_with_a_subscription_on_the_plan_offers_renew_or_new() -> None:
    manager = _manager(start_data=_LINK_START)

    await start_purchase_steps(manager, _catalog(10), [_subscription(3, plan_id=10)])

    assert manager.dialog_data[LINK_CHOICE_KEY] is True
    manager.switch_to.assert_awaited_once_with(Purchase.LINK_CHOICE)


async def test_link_to_an_unavailable_plan_answers_and_opens_the_menu() -> None:
    manager = _manager(start_data=_LINK_START)
    manager.event = MagicMock(spec=Message)
    manager.event.answer = AsyncMock()
    list_active_plans = AsyncMock(return_value=_catalog())

    await on_purchase_start.__dishka_orig_func__(
        manager.start_data,
        manager,
        list_active_plans=list_active_plans,
        list_own_subscriptions=AsyncMock(return_value=[]),
        list_payment_methods=AsyncMock(),
        i18n=_i18n(),
    )

    list_active_plans.assert_awaited_once_with(
        manager.middleware_data[USER_KEY], ListActivePlansDto(plan_code="Ab12Cd34")
    )
    manager.event.answer.assert_awaited_once_with("ntf-purchase.plan-unavailable")
    manager.start.assert_awaited_once_with(MainMenu.MAIN, mode=StartMode.RESET_STACK)
    manager.done.assert_not_awaited()


async def test_renew_choice_targets_that_subscription() -> None:
    manager = _manager(dialog_data={PLAN_CODE_KEY: "Ab12Cd34", "purchase_type": "NEW"})
    manager.item_id = "3"

    await on_link_renew(MagicMock(), MagicMock(), manager)

    assert manager.dialog_data["purchase_type"] == PurchaseType.RENEW.value
    assert manager.dialog_data[SELECTED_SUBSCRIPTION_KEY] == 3
    manager.switch_to.assert_awaited_once_with(Purchase.DURATION)


async def test_new_choice_buys_a_separate_subscription() -> None:
    manager = _manager(
        dialog_data={PLAN_CODE_KEY: "x", "purchase_type": "RENEW", SELECTED_SUBSCRIPTION_KEY: 3}
    )

    await on_link_new(MagicMock(), MagicMock(), manager)

    assert manager.dialog_data["purchase_type"] == PurchaseType.NEW.value
    assert SELECTED_SUBSCRIPTION_KEY not in manager.dialog_data
    manager.switch_to.assert_awaited_once_with(Purchase.DURATION)


@pytest.mark.parametrize(
    ("choice", "expected"),
    [(True, ("switch_to", Purchase.LINK_CHOICE)), (False, ("start", MainMenu.MAIN))],
)
async def test_back_from_durations_of_a_link(choice: bool, expected: tuple[str, Any]) -> None:
    manager = _manager(dialog_data={PLAN_CODE_KEY: "x", LINK_CHOICE_KEY: choice})

    await on_duration_back(MagicMock(), MagicMock(), manager)

    method, state = expected
    assert getattr(manager, method).await_args.args[0] == state
    manager.done.assert_not_awaited()


async def test_confirm_sends_the_link_code_to_checkout() -> None:
    manager = _manager(dialog_data={**_confirm_data("NEW"), PLAN_CODE_KEY: "Ab12Cd34"})
    create_checkout = AsyncMock(
        return_value=CheckoutResultDto(order_id=1, confirmation_url="https://pay")
    )

    await on_confirm.__dishka_orig_func__(
        MagicMock(), MagicMock(), manager, create_checkout=create_checkout, i18n=_i18n()
    )

    assert create_checkout.await_args.args[1].plan_code == "Ab12Cd34"


async def test_getters_ask_the_catalog_for_the_linked_plan() -> None:
    list_active_plans = AsyncMock(return_value=_catalog(10))
    manager = _getter_manager({"plan_id": 10, PLAN_CODE_KEY: "Ab12Cd34"})

    await duration_getter.__dishka_orig_func__(
        manager, list_active_plans=list_active_plans, i18n=_getter_i18n()
    )

    assert list_active_plans.await_args.args[1] == ListActivePlansDto(plan_code="Ab12Cd34")


async def test_link_choice_lists_only_subscriptions_on_that_plan() -> None:
    manager = _getter_manager({"plan_id": 10, PLAN_CODE_KEY: "x"})

    data = await link_choice_getter.__dishka_orig_func__(
        manager,
        list_active_plans=AsyncMock(return_value=_catalog(10)),
        list_own_subscriptions=AsyncMock(
            return_value=[_subscription(3, plan_id=10), _subscription(4, plan_id=11)]
        ),
        i18n=_getter_i18n(),
    )

    assert [item["id"] for item in data["subscriptions"]] == [3]
    assert data["subscriptions"][0]["label"] == _get(
        "btn-purchase.link-renew", subscription="Plan 10 — 01.11.2026"
    )
