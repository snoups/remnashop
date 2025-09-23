from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode, SubManager
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger
from pydantic import SecretStr

from src.bot.states import RemnashopGateways
from src.core.constants import USER_KEY
from src.core.enums import Currency
from src.core.utils.formatters import format_log_user
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import UserDto
from src.services.notification import NotificationService
from src.services.payment_gateway import PaymentGatewayService


@inject
async def on_gateway_selected(
    callback: CallbackQuery,
    widget: Button,
    sub_manager: SubManager,
    payment_gateway_service: FromDishka[PaymentGatewayService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = sub_manager.middleware_data[USER_KEY]
    gateway_id = int(sub_manager.item_id)
    gateway = await payment_gateway_service.get(gateway_id)

    if not gateway:
        return

    logger.debug(f"{format_log_user(user)} Gateway '{gateway_id}' selected")

    if not gateway.settings:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-gateway-not-configurable"),
        )
        return

    sub_manager.manager.dialog_data["gateway_id"] = gateway_id
    await sub_manager.switch_to(state=RemnashopGateways.SETTINGS)


@inject
async def on_gateway_test(
    callback: CallbackQuery,
    widget: Button,
    sub_manager: SubManager,
    payment_gateway_service: FromDishka[PaymentGatewayService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = sub_manager.middleware_data[USER_KEY]
    gateway_id = int(sub_manager.item_id)
    gateway = await payment_gateway_service.get(gateway_id)

    if not gateway:
        return

    logger.debug(f"{format_log_user(user)} Testing gateway '{gateway_id}'")

    try:
        payment_link = await payment_gateway_service.create_test_payment(gateway.type)

        logger.info("Test payment successful")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key="ntf-gateway-test-payment-success",
                i18n_kwargs={"url": payment_link},
            ),
        )

    except Exception as exception:
        logger.error(f"Test payment failed. Error: {exception}")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-gateway-test-payment-error"),
        )
        raise


@inject
async def on_active_toggle(
    callback: CallbackQuery,
    widget: Button,
    sub_manager: SubManager,
    payment_gateway_service: FromDishka[PaymentGatewayService],
    notification_service: FromDishka[NotificationService],
) -> None:
    await sub_manager.load_data()
    user: UserDto = sub_manager.middleware_data[USER_KEY]
    gateway_id = int(sub_manager.item_id)
    gateway = await payment_gateway_service.get(gateway_id)

    if not gateway:
        return

    if gateway.settings and not gateway.settings.is_configure:
        logger.warning(f"{format_log_user(user)} Gateway '{gateway_id}' is not configured")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-gateway-not-configured"),
        )
        return

    gateway.is_active = not gateway.is_active
    logger.debug(f"{format_log_user(user)} Toggling active state for gateway '{gateway_id}'")
    await payment_gateway_service.update(gateway)


async def on_field_selected(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_field: str,
) -> None:
    dialog_manager.dialog_data["selected_field"] = selected_field
    await dialog_manager.switch_to(state=RemnashopGateways.FIELD)


@inject
async def on_field_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    payment_gateway_service: FromDishka[PaymentGatewayService],
    notification_service: FromDishka[NotificationService],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    gateway_id = dialog_manager.dialog_data["gateway_id"]
    selected_field = dialog_manager.dialog_data["selected_field"]

    if message.text is None:
        logger.warning(f"{format_log_user(user)} Provided empty input for field '{selected_field}'")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-gateway-field-wrong-value"),
        )
        return

    gateway = await payment_gateway_service.get(gateway_id)

    if not gateway or not gateway.settings:
        logger.error(
            f"{format_log_user(user)} Attempted to update non-existent "
            f"gateway or settings for gateway '{gateway_id}'"
        )
        await dialog_manager.switch_to(state=RemnashopGateways.MAIN)
        return

    input_value = message.text

    if selected_field == "key":
        input_value = SecretStr(input_value)  # type: ignore[assignment]

    setattr(gateway.settings, selected_field, input_value)

    logger.debug(f"{format_log_user(user)} Changed '{selected_field}' for gateway '{gateway_id}'")
    await payment_gateway_service.update(gateway)
    await dialog_manager.switch_to(state=RemnashopGateways.SETTINGS)


@inject
async def on_default_currency_selected(
    callback: CallbackQuery,
    widget: Select[Currency],
    dialog_manager: DialogManager,
    selected_currency: Currency,
    payment_gateway_service: FromDishka[PaymentGatewayService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.debug(f"{format_log_user(user)} Set default currency '{selected_currency}'")
    await payment_gateway_service.set_default_currency(selected_currency)
