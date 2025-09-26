from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.kbd import Button, Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger

from src.bot.states import Subscription
from src.core.constants import USER_KEY
from src.core.enums import PaymentGatewayType
from src.core.utils.adapter import DialogDataAdapter
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import PlanDto, UserDto
from src.services.notification import NotificationService
from src.services.payment_gateway import PaymentGatewayService
from src.services.plan import PlanService


@inject
async def on_subscription_plans(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    plan_service: FromDishka[PlanService],
    payment_gateway_service: FromDishka[PaymentGatewayService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    plans: list[PlanDto] = await plan_service.get_available_plans(user)
    gateways = await payment_gateway_service.filter_active()

    if not plans:
        await notification_service.notify_user(
            user,
            MessagePayload(i18n_key="ntf-subscription-plans-not-available"),
        )
        return

    if not gateways:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-subscription-gateways-not-available"),
        )
        return

    if len(plans) == 1:
        adapter = DialogDataAdapter(dialog_manager)
        adapter.save(plans[0])
        dialog_manager.dialog_data["only_single_plan"] = True
        await dialog_manager.switch_to(state=Subscription.DURATION)
        return

    dialog_manager.dialog_data["only_single_plan"] = False
    await dialog_manager.switch_to(state=Subscription.PLANS)


@inject
async def on_plan_selected(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_plan: int,
    plan_service: FromDishka[PlanService],
) -> None:
    plan = await plan_service.get(plan_id=selected_plan)

    if not plan:
        return

    adapter = DialogDataAdapter(dialog_manager)
    adapter.save(plan)

    if len(plan.durations) == 1:
        await on_duration_selected(callback, widget, dialog_manager, plan.durations[0].days)
        return

    await dialog_manager.switch_to(state=Subscription.DURATION)


@inject
async def on_duration_selected(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_duration: int,
    payment_gateway_service: FromDishka[PaymentGatewayService],
) -> None:
    dialog_manager.dialog_data["selected_duration"] = selected_duration

    gateways = await payment_gateway_service.filter_active()
    if len(gateways) == 1:
        dialog_manager.dialog_data["selected_payment_method"] = gateways[0].type
        await dialog_manager.switch_to(state=Subscription.CONFIRM)
        return

    await dialog_manager.switch_to(state=Subscription.PAYMENT_METHOD)


async def on_payment_method_selected(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_payment_method: PaymentGatewayType,
) -> None:
    dialog_manager.dialog_data["selected_payment_method"] = selected_payment_method
    await dialog_manager.switch_to(state=Subscription.CONFIRM)


@inject
async def on_get_subscription(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    payment_gateway_service: FromDishka[PaymentGatewayService],
) -> None:
    payment_id = dialog_manager.dialog_data["payment_id"]
    await payment_gateway_service.handle_payment_succeeded(payment_id)
    return
