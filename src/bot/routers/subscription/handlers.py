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

    await dialog_manager.switch_to(state=Subscription.DURATION)


async def on_duration_selected(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_duration: int,
) -> None:
    dialog_manager.dialog_data["selected_duration"] = selected_duration
    await dialog_manager.switch_to(state=Subscription.PAYMENT_METHOD)


async def on_payment_method_selected(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_payment_method: PaymentGatewayType,
) -> None:
    dialog_manager.dialog_data["selected_payment_method"] = selected_payment_method
    await dialog_manager.switch_to(state=Subscription.CONFIRM)
