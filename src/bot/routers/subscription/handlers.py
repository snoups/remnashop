import traceback
from typing import Optional, TypedDict, cast

from aiogram.types import CallbackQuery
from aiogram.utils.formatting import Text
from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.kbd import Button, Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger

from src.bot.keyboards import get_user_keyboard
from src.bot.states import Subscription
from src.core.constants import PURCHASE_PREFIX, USER_KEY
from src.core.enums import PaymentGatewayType, PurchaseType
from src.core.utils.adapter import DialogDataAdapter
from src.core.utils.formatters import format_user_log as log
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import PlanDto, PlanSnapshotDto, UserDto
from src.services.notification import NotificationService
from src.services.payment_gateway import PaymentGatewayService
from src.services.plan import PlanService
from src.services.pricing import PricingService
from src.services.settings import SettingsService
from src.services.subscription import SubscriptionService

PAYMENT_CACHE_KEY = "payment_cache"
CURRENT_DURATION_KEY = "selected_duration"
CURRENT_METHOD_KEY = "selected_payment_method"


class CachedPaymentData(TypedDict):
    payment_id: str
    payment_url: Optional[str]
    final_pricing: str


def _get_cache_key(duration: int, gateway_type: PaymentGatewayType) -> str:
    return f"{duration}:{gateway_type.value}"


def _load_payment_data(dialog_manager: DialogManager) -> dict[str, CachedPaymentData]:
    if PAYMENT_CACHE_KEY not in dialog_manager.dialog_data:
        dialog_manager.dialog_data[PAYMENT_CACHE_KEY] = {}
    return cast(dict[str, CachedPaymentData], dialog_manager.dialog_data[PAYMENT_CACHE_KEY])


def _save_payment_data(dialog_manager: DialogManager, payment_data: CachedPaymentData) -> None:
    dialog_manager.dialog_data["payment_id"] = payment_data["payment_id"]
    dialog_manager.dialog_data["payment_url"] = payment_data["payment_url"]
    dialog_manager.dialog_data["final_pricing"] = payment_data["final_pricing"]


async def _create_payment_and_get_data(
    dialog_manager: DialogManager,
    plan: PlanDto,
    duration_days: int,
    gateway_type: PaymentGatewayType,
    payment_gateway_service: PaymentGatewayService,
    notification_service: NotificationService,
    pricing_service: PricingService,
) -> Optional[CachedPaymentData]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    duration = plan.get_duration(duration_days)
    payment_gateway = await payment_gateway_service.get_by_type(gateway_type)
    purchase_type: PurchaseType = dialog_manager.dialog_data["purchase_type"]

    if not duration or not payment_gateway:
        logger.error(f"{log(user)} Failed to find duration or gateway for payment creation")
        return None

    transaction_plan = PlanSnapshotDto.from_plan(plan, duration.days)
    price = duration.get_price(payment_gateway.currency)
    pricing = pricing_service.calculate(user, price, payment_gateway.currency)

    try:
        result = await payment_gateway_service.create_payment(
            user=user,
            plan=transaction_plan,
            pricing=pricing,
            purchase_type=purchase_type,
            gateway_type=gateway_type,
        )

        return CachedPaymentData(
            payment_id=str(result.id),
            payment_url=result.url,
            final_pricing=pricing.model_dump_json(),
        )

    except Exception as exception:
        logger.error(f"{log(user)} Failed to create payment: {exception}")
        traceback_str = traceback.format_exc()
        error_type_name = type(exception).__name__
        error_message = Text(str(exception)[:512])

        await notification_service.error_notify(
            error_id=user.telegram_id,
            traceback_str=traceback_str,
            payload=MessagePayload.not_deleted(
                i18n_key="ntf-event-error",
                i18n_kwargs={
                    "user": True,
                    "user_id": str(user.telegram_id),
                    "user_name": user.name,
                    "username": user.username or False,
                    "error": f"{error_type_name}: Failed to create payment "
                    + f"check due to error: {error_message.as_html()}",
                },
                reply_markup=get_user_keyboard(user.telegram_id),
            ),
        )

        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-subscription-payment-creation-failed"),
        )
        return None


@inject
async def on_purchase_type_select(
    purchase_type: PurchaseType,
    dialog_manager: DialogManager,
    plan_service: FromDishka[PlanService],
    payment_gateway_service: FromDishka[PaymentGatewayService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    plans: list[PlanDto] = await plan_service.get_available_plans(user)
    gateways = await payment_gateway_service.filter_active()
    dialog_manager.dialog_data["purchase_type"] = purchase_type
    dialog_manager.dialog_data.pop(CURRENT_DURATION_KEY, None)

    if not plans:
        logger.warning(f"{log(user)} No available subscription plans")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-subscription-plans-not-available"),
        )
        return

    if not gateways:
        logger.warning(f"{log(user)} No active payment gateways")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-subscription-gateways-not-available"),
        )
        return

    adapter = DialogDataAdapter(dialog_manager)

    if purchase_type == PurchaseType.RENEW:
        if user.current_subscription:
            matched_plan = SubscriptionService.find_matching_plan(
                plan_snapshot=user.current_subscription.plan,
                plans=plans,
            )
            logger.debug(f"Matched plan for renewal: '{matched_plan}'")

            if matched_plan:
                adapter.save(matched_plan)
                dialog_manager.dialog_data["only_single_plan"] = True
                await dialog_manager.switch_to(state=Subscription.DURATION)
                return
            else:
                logger.warning(f"{log(user)} Tried to renew, but no matching plan found")
                await notification_service.notify_user(
                    user=user,
                    payload=MessagePayload(i18n_key="ntf-subscription-renew-plan-unavailable"),
                )
                return

    if len(plans) == 1:
        logger.info(f"{log(user)} Auto-selected single plan '{plans[0].id}'")
        adapter.save(plans[0])
        dialog_manager.dialog_data["only_single_plan"] = True
        await dialog_manager.switch_to(state=Subscription.DURATION)
        return

    dialog_manager.dialog_data["only_single_plan"] = False
    await dialog_manager.switch_to(state=Subscription.PLANS)


@inject
async def on_subscription_plans(  # noqa: C901
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    plan_service: FromDishka[PlanService],
    payment_gateway_service: FromDishka[PaymentGatewayService],
    notification_service: FromDishka[NotificationService],
    pricing_service: FromDishka[PricingService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{log(user)} Opened subscription plans menu")

    plans: list[PlanDto] = await plan_service.get_available_plans(user)
    gateways = await payment_gateway_service.filter_active()

    if not callback.data:
        raise ValueError("Callback data is empty")

    purchase_type = PurchaseType(callback.data.removeprefix(PURCHASE_PREFIX))
    dialog_manager.dialog_data["purchase_type"] = purchase_type

    dialog_manager.dialog_data.pop(CURRENT_DURATION_KEY, None)

    if not plans:
        logger.warning(f"{log(user)} No available subscription plans")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-subscription-plans-not-available"),
        )
        return

    if not gateways:
        logger.warning(f"{log(user)} No active payment gateways")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-subscription-gateways-not-available"),
        )
        return

    adapter = DialogDataAdapter(dialog_manager)

    if purchase_type == PurchaseType.RENEW:
        if user.current_subscription:
            matched_plan = SubscriptionService.find_matching_plan(
                plan_snapshot=user.current_subscription.plan,
                plans=plans,
            )
            logger.debug(f"Matched plan for renewal: '{matched_plan}'")

            if matched_plan:
                adapter.save(matched_plan)
                dialog_manager.dialog_data["only_single_plan"] = True
                await dialog_manager.switch_to(state=Subscription.DURATION)
                return
            else:
                logger.warning(f"{log(user)} Tried to renew, but no matching plan found")
                await notification_service.notify_user(
                    user=user,
                    payload=MessagePayload(i18n_key="ntf-subscription-renew-plan-unavailable"),
                )
                return

    if len(plans) == 1:
        logger.info(f"{log(user)} Auto-selected single plan '{plans[0].id}'")
        adapter.save(plans[0])
        dialog_manager.dialog_data["only_single_plan"] = True

        if len(plans[0].durations) == 1:
            logger.info(f"{log(user)} Auto-selected duration '{plans[0].durations[0].days}'")
            dialog_manager.dialog_data["selected_duration"] = plans[0].durations[0].days
            dialog_manager.dialog_data["only_single_duration"] = True

            if len(gateways) == 1:
                logger.info(f"{log(user)} Auto-selected payment method '{gateways[0].type}'")
                dialog_manager.dialog_data["selected_payment_method"] = gateways[0].type
                dialog_manager.dialog_data["only_single_payment_method"] = True

                payment_data = await _create_payment_and_get_data(
                    dialog_manager=dialog_manager,
                    plan=plans[0],
                    duration_days=plans[0].durations[0].days,
                    gateway_type=gateways[0].type,
                    payment_gateway_service=payment_gateway_service,
                    notification_service=notification_service,
                    pricing_service=pricing_service,
                )

                if payment_data:
                    _save_payment_data(dialog_manager, payment_data)

                await dialog_manager.switch_to(state=Subscription.CONFIRM)
                return

            await dialog_manager.switch_to(state=Subscription.PAYMENT_METHOD)
            return

        await dialog_manager.switch_to(state=Subscription.DURATION)
        return

    dialog_manager.dialog_data["only_single_plan"] = False
    dialog_manager.dialog_data["only_single_duration"] = False
    await dialog_manager.switch_to(state=Subscription.PLANS)


@inject
async def on_plan_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_plan: int,
    plan_service: FromDishka[PlanService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    plan = await plan_service.get(plan_id=selected_plan)

    if not plan:
        raise ValueError(f"Selected plan '{selected_plan}' not found")

    logger.info(f"{log(user)} Selected plan '{plan.id}'")
    adapter = DialogDataAdapter(dialog_manager)
    adapter.save(plan)

    dialog_manager.dialog_data.pop(PAYMENT_CACHE_KEY, None)
    dialog_manager.dialog_data.pop(CURRENT_DURATION_KEY, None)
    dialog_manager.dialog_data.pop(CURRENT_METHOD_KEY, None)

    if len(plan.durations) == 1:
        logger.info(f"{log(user)} Auto-selected single duration '{plan.durations[0].days}'")
        dialog_manager.dialog_data["only_single_duration"] = True
        await on_duration_select(callback, widget, dialog_manager, plan.durations[0].days)
        return

    await dialog_manager.switch_to(state=Subscription.DURATION)


@inject
async def on_duration_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_duration: int,
    settings_service: FromDishka[SettingsService],
    payment_gateway_service: FromDishka[PaymentGatewayService],
    notification_service: FromDishka[NotificationService],
    pricing_service: FromDishka[PricingService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{log(user)} Selected subscription duration '{selected_duration}' days")
    dialog_manager.dialog_data[CURRENT_DURATION_KEY] = selected_duration

    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    gateways = await payment_gateway_service.filter_active()
    currency = await settings_service.get_default_currency()
    price = pricing_service.calculate(
        user=user,
        price=plan.get_duration(selected_duration).get_price(currency),  # type: ignore[union-attr]
        currency=currency,
    )
    dialog_manager.dialog_data["is_free"] = price.is_free

    if len(gateways) == 1 or price.is_free:
        selected_payment_method = gateways[0].type
        dialog_manager.dialog_data[CURRENT_METHOD_KEY] = selected_payment_method

        cache = _load_payment_data(dialog_manager)
        cache_key = _get_cache_key(selected_duration, selected_payment_method)

        if cache_key in cache:
            logger.info(f"{log(user)} Re-selected same duration and single gateway")
            _save_payment_data(dialog_manager, cache[cache_key])
            await dialog_manager.switch_to(state=Subscription.CONFIRM)
            return

        logger.info(f"{log(user)} Auto-selected single gateway '{selected_payment_method}'")

        payment_data = await _create_payment_and_get_data(
            dialog_manager=dialog_manager,
            plan=plan,
            duration_days=selected_duration,
            gateway_type=selected_payment_method,
            payment_gateway_service=payment_gateway_service,
            notification_service=notification_service,
            pricing_service=pricing_service,
        )

        if payment_data:
            cache[cache_key] = payment_data
            _save_payment_data(dialog_manager, payment_data)
            await dialog_manager.switch_to(state=Subscription.CONFIRM)
            return

    dialog_manager.dialog_data.pop(CURRENT_METHOD_KEY, None)
    await dialog_manager.switch_to(state=Subscription.PAYMENT_METHOD)


@inject
async def on_payment_method_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_payment_method: PaymentGatewayType,
    payment_gateway_service: FromDishka[PaymentGatewayService],
    notification_service: FromDishka[NotificationService],
    pricing_service: FromDishka[PricingService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{log(user)} Selected payment method '{selected_payment_method}'")

    selected_duration = dialog_manager.dialog_data[CURRENT_DURATION_KEY]
    dialog_manager.dialog_data[CURRENT_METHOD_KEY] = selected_payment_method
    cache = _load_payment_data(dialog_manager)
    cache_key = _get_cache_key(selected_duration, selected_payment_method)

    if cache_key in cache:
        logger.info(f"{log(user)} Re-selected same method and duration")
        _save_payment_data(dialog_manager, cache[cache_key])
        await dialog_manager.switch_to(state=Subscription.CONFIRM)
        return

    logger.info(f"{log(user)} New combination. Creating new payment")

    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    payment_data = await _create_payment_and_get_data(
        dialog_manager=dialog_manager,
        plan=plan,
        duration_days=selected_duration,
        gateway_type=selected_payment_method,
        payment_gateway_service=payment_gateway_service,
        notification_service=notification_service,
        pricing_service=pricing_service,
    )

    if payment_data:
        cache[cache_key] = payment_data
        _save_payment_data(dialog_manager, payment_data)

    await dialog_manager.switch_to(state=Subscription.CONFIRM)


@inject
async def on_get_subscription(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    payment_gateway_service: FromDishka[PaymentGatewayService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    payment_id = dialog_manager.dialog_data["payment_id"]
    logger.info(f"{log(user)} Getted free subscription '{payment_id}'")
    await payment_gateway_service.handle_payment_succeeded(payment_id)
