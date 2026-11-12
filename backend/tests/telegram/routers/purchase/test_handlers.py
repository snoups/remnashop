from decimal import Decimal
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import CallbackQuery
from aiogram_dialog import StartMode
from fluent.syntax import FluentParser, ast
from remnapy.enums import TrafficLimitStrategy

from app.core.constants import USER_KEY
from app.core.enums import (
    Currency,
    Locale,
    PaymentGatewayType,
    PlanType,
    PurchaseChannel,
    PurchaseType,
)
from app.core.error_codes import ErrorCode
from app.core.exceptions import PaymentGatewayError, PermissionDeniedError, ValidationError
from app.modules.dialogs import catalog
from app.modules.subscriptions import CatalogDurationDto, CatalogPlanDto, PlanCatalogDto
from app.modules.subscriptions.dto import CatalogPriceDto
from app.modules.transactions import CreateCheckoutDto, PaymentMethodDto
from app.modules.transactions.dto import CheckoutResultDto
from app.telegram.dialogs import state_pool
from app.telegram.dialogs.context import SELECTED_SUBSCRIPTION_KEY
from app.telegram.i18n import format_price
from app.telegram.routers.purchase.catalog import register_purchase_catalog
from app.telegram.routers.purchase.handlers import (
    PAYMENT_URL_KEY,
    checkout_error_key,
    on_confirm,
    on_duration_selected,
    on_method_selected,
    on_purchase_change,
    on_purchase_new,
    on_purchase_renew,
    on_purchase_start,
    plans_for,
    price_in,
    select_duration,
    start_purchase_steps,
)
from app.telegram.states import MainMenu, Purchase

_LOCALES_DIR = Path(__file__).parents[4] / "assets" / "translations"


def _duration(days: int = 30, rub: str = "199", usd: str = "2.5") -> CatalogDurationDto:
    return CatalogDurationDto(
        days=days,
        order_index=0,
        prices=[
            CatalogPriceDto(currency=Currency.RUB, price=Decimal(rub)),
            CatalogPriceDto(currency=Currency.USD, price=Decimal(usd)),
        ],
    )


def _plan(id: int, durations: Optional[list[CatalogDurationDto]] = None) -> CatalogPlanDto:
    return CatalogPlanDto(
        id=id,
        name=f"Plan {id}",
        description=None,
        badge=None,
        type=PlanType.UNLIMITED,
        traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
        traffic_limit=0,
        device_limit=0,
        is_trial=False,
        order_index=0,
        durations=durations if durations is not None else [_duration()],
    )


def _manager(start_data: object = None, dialog_data: Optional[dict] = None) -> AsyncMock:
    manager = AsyncMock()
    manager.middleware_data = {USER_KEY: MagicMock(id=1, language=Locale.EN)}
    manager.start_data = start_data
    manager.dialog_data = dialog_data if dialog_data is not None else {}
    return manager


def _quote(final: str = "199", base: str = "199") -> AsyncMock:
    return AsyncMock(return_value=MagicMock(final_price=Decimal(final), base_price=Decimal(base)))


_quote_checkout = _quote


def _i18n() -> MagicMock:
    i18n = MagicMock()
    i18n.get_translator_by_locale.return_value = MagicMock(get=lambda key, **kwargs: key)
    return i18n


async def test_renew_skips_the_plan_step() -> None:
    manager = _manager(start_data={"purchase_type": "RENEW", SELECTED_SUBSCRIPTION_KEY: 3})
    catalog_dto = PlanCatalogDto(plans=[_plan(id=10)], anchor_currency=Currency.RUB)
    subscriptions = [MagicMock(id=3, plan_snapshot=MagicMock(plan_id=10))]

    await start_purchase_steps(manager, catalog_dto, subscriptions)

    assert manager.dialog_data["plan_id"] == 10
    manager.switch_to.assert_awaited_once_with(Purchase.DURATION)


async def test_renew_of_a_plan_gone_from_the_catalog_answers_an_alert() -> None:
    manager = _manager(start_data={"purchase_type": "RENEW", SELECTED_SUBSCRIPTION_KEY: 3})
    catalog_dto = PlanCatalogDto(plans=[_plan(id=11)], anchor_currency=Currency.RUB)
    subscriptions = [MagicMock(id=3, plan_snapshot=MagicMock(plan_id=10))]

    assert (
        await start_purchase_steps(manager, catalog_dto, subscriptions)
        == "ntf-purchase.plan-unavailable"
    )


async def test_renew_of_a_gone_subscription_answers_an_alert() -> None:
    manager = _manager(start_data={"purchase_type": "RENEW", SELECTED_SUBSCRIPTION_KEY: 3})
    catalog_dto = PlanCatalogDto(plans=[_plan(id=10)], anchor_currency=Currency.RUB)

    assert await start_purchase_steps(manager, catalog_dto, []) == "ntf-subscription.gone"


async def test_new_purchase_starts_at_the_plan_step() -> None:
    manager = _manager(start_data={"purchase_type": "NEW"})
    catalog_dto = PlanCatalogDto(plans=[_plan(id=10)], anchor_currency=Currency.RUB)

    assert await start_purchase_steps(manager, catalog_dto, []) is None
    manager.switch_to.assert_awaited_once_with(Purchase.PLAN)


async def test_change_with_only_the_current_plan_has_nothing_to_offer() -> None:
    manager = _manager(start_data={"purchase_type": "CHANGE", SELECTED_SUBSCRIPTION_KEY: 3})
    catalog_dto = PlanCatalogDto(plans=[_plan(id=10)], anchor_currency=Currency.RUB)
    subscriptions = [MagicMock(id=3, plan_snapshot=MagicMock(plan_id=10))]

    key = await start_purchase_steps(manager, catalog_dto, subscriptions)
    assert key == "ntf-purchase.no-plans"


async def test_change_hides_the_current_plan() -> None:
    plans = plans_for(
        PurchaseType.CHANGE,
        PlanCatalogDto(plans=[_plan(id=10), _plan(id=11)], anchor_currency=Currency.RUB),
        current_plan_id=10,
    )
    assert [p.id for p in plans] == [11]


async def test_checkout_error_maps_to_a_notification_key() -> None:
    assert checkout_error_key(PermissionDeniedError("x", code=ErrorCode.PAYMENTS_DISABLED)) == (
        "ntf-purchase.payments-disabled"
    )
    assert checkout_error_key(PaymentGatewayError("x")) == "ntf-purchase.failed"


def test_price_label_uses_the_anchor_currency() -> None:
    assert price_in(_duration(), Currency.RUB) == Decimal("199")


@pytest.mark.parametrize(
    ("price", "expected"),
    [(Decimal("199"), "199"), (Decimal("199.00"), "199"), (Decimal("2.5"), "2.50")],
)
def test_format_price_drops_only_zero_cents(price: Decimal, expected: str) -> None:
    assert format_price(price) == expected


async def test_start_failure_answers_the_callback_and_closes() -> None:
    manager = _manager(start_data={"purchase_type": "RENEW", SELECTED_SUBSCRIPTION_KEY: 3})
    manager.event = MagicMock(spec=CallbackQuery)
    manager.event.answer = AsyncMock()

    await on_purchase_start.__dishka_orig_func__(
        manager.start_data,
        manager,
        list_active_plans=AsyncMock(
            return_value=PlanCatalogDto(plans=[], anchor_currency=Currency.RUB)
        ),
        list_own_subscriptions=AsyncMock(return_value=[]),
        list_payment_methods=AsyncMock(),
        quote_checkout=_quote_checkout(),
        i18n=_i18n(),
    )

    manager.event.answer.assert_awaited_once_with("ntf-subscription.gone", show_alert=True)
    manager.done.assert_awaited_once()


async def test_new_purchase_start_does_not_list_subscriptions() -> None:
    manager = _manager(start_data={"purchase_type": "NEW"})
    list_own = AsyncMock()

    await on_purchase_start.__dishka_orig_func__(
        manager.start_data,
        manager,
        list_active_plans=AsyncMock(
            return_value=PlanCatalogDto(plans=[_plan(id=10)], anchor_currency=Currency.RUB)
        ),
        list_own_subscriptions=list_own,
        list_payment_methods=AsyncMock(),
        quote_checkout=_quote_checkout(),
        i18n=_i18n(),
    )

    list_own.assert_not_awaited()
    manager.switch_to.assert_awaited_once_with(Purchase.PLAN)


_RUB_METHOD = PaymentMethodDto(gateway_type=PaymentGatewayType.YOOKASSA, currency=Currency.RUB)
_STARS_METHOD = PaymentMethodDto(
    gateway_type=PaymentGatewayType.TELEGRAM_STARS, currency=Currency.XTR
)


async def test_one_method_skips_the_method_step() -> None:
    manager = _manager(dialog_data={"plan_id": 10})
    catalog_dto = PlanCatalogDto(plans=[_plan(id=10)], anchor_currency=Currency.RUB)

    assert await select_duration(manager, catalog_dto, 30, [_RUB_METHOD], _quote()) is None

    assert manager.dialog_data["gateway_type"] == "YOOKASSA"
    assert manager.dialog_data["currency"] == "RUB"
    assert manager.dialog_data["duration_days"] == 30
    manager.switch_to.assert_awaited_once_with(Purchase.CONFIRM)


async def test_several_methods_open_the_method_step() -> None:
    manager = _manager(dialog_data={"plan_id": 10})
    catalog_dto = PlanCatalogDto(plans=[_plan(id=10)], anchor_currency=Currency.RUB)

    assert (
        await select_duration(manager, catalog_dto, 30, [_RUB_METHOD, _STARS_METHOD], _quote())
        is None
    )

    assert "gateway_type" not in manager.dialog_data
    manager.switch_to.assert_awaited_once_with(Purchase.METHOD)


async def test_a_free_duration_picks_the_first_method_silently() -> None:
    manager = _manager(dialog_data={"plan_id": 10})
    free = _plan(id=10, durations=[_duration(rub="0", usd="0")])
    catalog_dto = PlanCatalogDto(plans=[free], anchor_currency=Currency.RUB)

    await select_duration(manager, catalog_dto, 30, [_STARS_METHOD, _RUB_METHOD], _quote("0"))

    assert manager.dialog_data["gateway_type"] == "TELEGRAM_STARS"
    manager.switch_to.assert_awaited_once_with(Purchase.CONFIRM)


async def test_no_methods_answer_an_alert() -> None:
    manager = _manager(dialog_data={"plan_id": 10})
    catalog_dto = PlanCatalogDto(plans=[_plan(id=10)], anchor_currency=Currency.RUB)

    assert (
        await select_duration(manager, catalog_dto, 30, [], _quote()) == "ntf-purchase.no-methods"
    )
    manager.switch_to.assert_not_awaited()


async def test_a_duration_gone_from_the_catalog_answers_an_alert() -> None:
    manager = _manager(dialog_data={"plan_id": 10})
    catalog_dto = PlanCatalogDto(plans=[_plan(id=10)], anchor_currency=Currency.RUB)

    assert await select_duration(manager, catalog_dto, 90, [_RUB_METHOD], _quote()) == (
        "ntf-purchase.plan-unavailable"
    )


def _confirm_data(purchase_type: str) -> dict:
    return {
        "purchase_type": purchase_type,
        "plan_id": 10,
        "duration_days": 30,
        "currency": "RUB",
        "gateway_type": "YOOKASSA",
    }


async def test_confirm_with_a_payment_link_opens_the_pay_step() -> None:
    manager = _manager(
        start_data={SELECTED_SUBSCRIPTION_KEY: 3}, dialog_data=_confirm_data("RENEW")
    )
    create_checkout = AsyncMock(
        return_value=CheckoutResultDto(order_id=1, confirmation_url="https://pay")
    )

    await on_confirm.__dishka_orig_func__(
        MagicMock(), MagicMock(), manager, create_checkout=create_checkout, i18n=_i18n()
    )

    create_checkout.assert_awaited_once_with(
        manager.middleware_data[USER_KEY],
        CreateCheckoutDto(
            channel=PurchaseChannel.BOT,
            plan_id=10,
            duration_days=30,
            currency=Currency.RUB,
            purchase_type=PurchaseType.RENEW,
            gateway_type=PaymentGatewayType.YOOKASSA,
            target_subscription_id=3,
        ),
    )
    assert manager.dialog_data["payment_url"] == "https://pay"
    manager.switch_to.assert_awaited_once_with(Purchase.PAY)


async def test_confirm_of_a_new_purchase_has_no_target() -> None:
    manager = _manager(start_data={"purchase_type": "NEW"}, dialog_data=_confirm_data("NEW"))
    create_checkout = AsyncMock(
        return_value=CheckoutResultDto(order_id=1, confirmation_url="https://pay")
    )

    await on_confirm.__dishka_orig_func__(
        MagicMock(), MagicMock(), manager, create_checkout=create_checkout, i18n=_i18n()
    )

    assert create_checkout.await_args.args[1].target_subscription_id is None


async def test_confirm_of_a_free_order_returns_to_the_menu() -> None:
    manager = _manager(dialog_data=_confirm_data("NEW"))
    callback = MagicMock()
    callback.answer = AsyncMock()

    await on_confirm.__dishka_orig_func__(
        callback,
        MagicMock(),
        manager,
        create_checkout=AsyncMock(return_value=CheckoutResultDto(order_id=1)),
        i18n=_i18n(),
    )

    callback.answer.assert_awaited_once_with()
    manager.start.assert_awaited_once_with(MainMenu.MAIN, mode=StartMode.RESET_STACK)


async def test_confirm_refusal_answers_its_key_and_stays() -> None:
    manager = _manager(dialog_data=_confirm_data("NEW"))
    callback = MagicMock()
    callback.answer = AsyncMock()
    error = PermissionDeniedError("x", code=ErrorCode.SUBSCRIPTION_LIMIT_REACHED)

    await on_confirm.__dishka_orig_func__(
        callback,
        MagicMock(),
        manager,
        create_checkout=AsyncMock(side_effect=error),
        i18n=_i18n(),
    )

    callback.answer.assert_awaited_once_with("ntf-purchase.limit-reached", show_alert=True)
    manager.switch_to.assert_not_awaited()
    manager.start.assert_not_awaited()


async def test_confirm_again_reuses_the_created_order() -> None:
    manager = _manager(dialog_data={**_confirm_data("NEW"), PAYMENT_URL_KEY: "https://pay"})
    create_checkout = AsyncMock()

    await on_confirm.__dishka_orig_func__(
        MagicMock(), MagicMock(), manager, create_checkout=create_checkout, i18n=_i18n()
    )

    create_checkout.assert_not_awaited()
    manager.switch_to.assert_awaited_once_with(Purchase.PAY)


@pytest.mark.parametrize("methods", [[_RUB_METHOD], [_RUB_METHOD, _STARS_METHOD]])
async def test_selecting_a_duration_again_forgets_the_created_order(
    methods: list[PaymentMethodDto],
) -> None:
    manager = _manager(dialog_data={"plan_id": 10, PAYMENT_URL_KEY: "https://pay"})
    catalog_dto = PlanCatalogDto(plans=[_plan(id=10)], anchor_currency=Currency.RUB)

    await select_duration(manager, catalog_dto, 30, methods, _quote())

    assert PAYMENT_URL_KEY not in manager.dialog_data


async def test_duration_hides_receipt_gateways_from_a_user_without_email() -> None:
    manager = _manager(dialog_data={"plan_id": 10})
    manager.item_id = "30"
    manager.middleware_data[USER_KEY].email = None
    receipt = PaymentMethodDto(
        gateway_type=PaymentGatewayType.YOOKASSA, currency=Currency.RUB, requires_email=True
    )
    list_active_plans = AsyncMock(
        return_value=PlanCatalogDto(plans=[_plan(id=10)], anchor_currency=Currency.RUB)
    )

    await on_duration_selected.__dishka_orig_func__(
        MagicMock(),
        MagicMock(),
        manager,
        list_active_plans=list_active_plans,
        list_payment_methods=AsyncMock(return_value=[receipt, _STARS_METHOD]),
        quote_checkout=_quote_checkout(),
        i18n=_i18n(),
    )

    assert manager.dialog_data["methods"] == [{"gateway_type": "TELEGRAM_STARS", "currency": "XTR"}]


async def test_selecting_a_method_again_forgets_the_created_order() -> None:
    manager = _manager(
        dialog_data={
            "methods": [{"gateway_type": "YOOKASSA", "currency": "RUB"}],
            PAYMENT_URL_KEY: "https://pay",
        }
    )
    manager.item_id = "YOOKASSA"

    await on_method_selected(MagicMock(), MagicMock(), manager)

    assert PAYMENT_URL_KEY not in manager.dialog_data
    manager.switch_to.assert_awaited_once_with(Purchase.CONFIRM)


async def test_purchase_actions_stack_the_dialog_with_their_type() -> None:
    manager = _manager(dialog_data={SELECTED_SUBSCRIPTION_KEY: 3})

    await on_purchase_new(MagicMock(), MagicMock(), manager)
    await on_purchase_renew(MagicMock(), MagicMock(), manager)
    await on_purchase_change(MagicMock(), MagicMock(), manager)

    assert [c.args for c in manager.start.await_args_list] == [(Purchase.PLAN,)] * 3
    assert [c.kwargs for c in manager.start.await_args_list] == [
        {"data": {"purchase_type": "NEW"}},
        {"data": {"purchase_type": "RENEW", SELECTED_SUBSCRIPTION_KEY: 3}},
        {"data": {"purchase_type": "CHANGE", SELECTED_SUBSCRIPTION_KEY: 3}},
    ]


def test_catalog_binds_the_purchase_actions() -> None:
    catalog._reset_for_tests()
    state_pool._reset_for_tests()
    try:
        register_purchase_catalog()
        for key in ("purchase_new", "purchase_renew", "purchase_change"):
            assert catalog.has_action_handler(key) is True
    finally:
        catalog._reset_for_tests()
        state_pool._reset_for_tests()


_NOTIFICATION_ATTRIBUTES = (
    "stars-rejected",
    "payments-disabled",
    "plan-unavailable",
    "limit-reached",
    "method-unavailable",
    "retry",
    "failed",
    "no-plans",
    "no-methods",
)


def _attributes(locale: str) -> dict[str, set[str]]:
    resource = FluentParser().parse((_LOCALES_DIR / locale / "menu.ftl").read_text())
    return {
        entry.id.name: {attribute.id.name for attribute in entry.attributes}
        for entry in resource.body
        if isinstance(entry, ast.Message)
    }


@pytest.mark.parametrize("locale", ["en", "ru"])
def test_purchase_texts_exist_in_each_locale(locale: str) -> None:
    messages = _attributes(locale)

    assert set(_NOTIFICATION_ATTRIBUTES) <= messages["ntf-purchase"]
    assert {g.value for g in PaymentGatewayType} <= messages["gateway-name"]
    assert {
        "pay",
        "go-to-payment",
        "menu",
        "duration",
        "method",
        "link-renew",
        "link-new",
    } <= messages["btn-purchase"]
    assert {
        "msg-purchase-plan",
        "msg-purchase-duration",
        "msg-purchase-method",
        "msg-purchase-confirm",
        "msg-purchase-pay",
        "msg-purchase-link-choice",
    } <= messages.keys()


async def _retry_start(manager: AsyncMock, methods: list[PaymentMethodDto], plans: list):
    await on_purchase_start.__dishka_orig_func__(
        manager.start_data,
        manager,
        list_active_plans=AsyncMock(
            return_value=PlanCatalogDto(plans=plans, anchor_currency=Currency.RUB)
        ),
        list_own_subscriptions=AsyncMock(return_value=[]),
        list_payment_methods=AsyncMock(return_value=methods),
        quote_checkout=_quote_checkout(),
        i18n=_i18n(),
    )


_RETRY = {"purchase_type": "NEW", "retry_plan_id": 10, "retry_duration_days": 30}


async def test_retry_start_skips_to_method() -> None:
    manager = _manager(start_data=_RETRY)

    await _retry_start(manager, [_RUB_METHOD, _STARS_METHOD], [_plan(id=10)])

    assert manager.dialog_data["duration_days"] == 30
    manager.switch_to.assert_awaited_once_with(Purchase.METHOD)


async def test_retry_start_with_one_method_goes_to_confirm() -> None:
    manager = _manager(start_data=_RETRY)

    await _retry_start(manager, [_RUB_METHOD], [_plan(id=10)])

    manager.switch_to.assert_awaited_once_with(Purchase.CONFIRM)


async def test_retry_with_unavailable_plan_alerts() -> None:
    manager = _manager(start_data=_RETRY)
    manager.event = MagicMock(spec=CallbackQuery)
    manager.event.answer = AsyncMock()

    await _retry_start(manager, [_RUB_METHOD], [_plan(id=11)])

    manager.event.answer.assert_awaited_once_with("ntf-purchase.plan-unavailable", show_alert=True)
    manager.start.assert_awaited_once_with(MainMenu.MAIN, mode=StartMode.RESET_STACK)


def _target(plan_id: int = 10) -> MagicMock:
    return MagicMock(id=3, plan_snapshot=MagicMock(plan_id=plan_id))


async def test_retry_of_a_renewal_checks_the_target() -> None:
    start = {**_RETRY, "purchase_type": "RENEW", SELECTED_SUBSCRIPTION_KEY: 3}
    catalog_dto = PlanCatalogDto(plans=[_plan(id=10)], anchor_currency=Currency.RUB)
    manager = _manager(start_data=start)

    assert await start_purchase_steps(manager, catalog_dto, [], [_RUB_METHOD], _quote()) == (
        "ntf-subscription.gone"
    )
    assert (
        await start_purchase_steps(manager, catalog_dto, [_target()], [_RUB_METHOD], _quote())
        is None
    )
    manager.switch_to.assert_awaited_once_with(Purchase.CONFIRM)


async def test_retry_of_a_change_to_the_current_plan_is_unavailable() -> None:
    start = {**_RETRY, "purchase_type": "CHANGE", SELECTED_SUBSCRIPTION_KEY: 3}
    catalog_dto = PlanCatalogDto(plans=[_plan(id=10), _plan(id=11)], anchor_currency=Currency.RUB)
    manager = _manager(start_data=start)

    assert await start_purchase_steps(
        manager, catalog_dto, [_target(10)], [_RUB_METHOD], _quote()
    ) == ("ntf-purchase.plan-unavailable")
    assert (
        await start_purchase_steps(manager, catalog_dto, [_target(11)], [_RUB_METHOD], _quote())
        is None
    )


async def test_duration_stores_the_price_checkout_will_charge() -> None:
    # a personal discount is in the quote, not in the catalog
    manager = _manager(dialog_data={"plan_id": 10})
    catalog_dto = PlanCatalogDto(plans=[_plan(id=10)], anchor_currency=Currency.RUB)

    await select_duration(manager, catalog_dto, 30, [_RUB_METHOD], _quote("159.2", "199"))

    assert manager.dialog_data["prices"] == {"RUB": "159.2"}
    assert manager.dialog_data["base_prices"] == {"RUB": "199"}


async def test_a_refused_quote_answers_an_alert() -> None:
    manager = _manager(dialog_data={"plan_id": 10})
    catalog_dto = PlanCatalogDto(plans=[_plan(id=10)], anchor_currency=Currency.RUB)
    quote = AsyncMock(side_effect=ValidationError("gone", code=ErrorCode.PLAN_NOT_AVAILABLE))

    assert await select_duration(manager, catalog_dto, 30, [_RUB_METHOD], quote) == (
        "ntf-purchase.plan-unavailable"
    )
    manager.switch_to.assert_not_awaited()
