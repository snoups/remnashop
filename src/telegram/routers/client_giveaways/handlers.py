from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, StartMode
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.application.common import Notifier
from src.application.dto import MessagePayloadDto, UserDto
from src.application.use_cases.giveaway.commands import (
    SaveGiveawayPhone,
    SaveGiveawayPhoneDto,
)
from src.application.use_cases.giveaway.queries import GetClientGiveawayDetails
from src.core.constants import USER_KEY
from src.telegram.states import ClientGiveaways, Subscription


async def on_client_campaign_select(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    dialog_manager.dialog_data["campaign_id"] = int(dialog_manager.item_id)  # type: ignore[attr-defined]
    await dialog_manager.switch_to(ClientGiveaways.VIEW)


@inject
async def on_buy_for_giveaway(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    get_details: FromDishka[GetClientGiveawayDetails],
    notifier: FromDishka[Notifier],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    details = await get_details(user, int(dialog_manager.dialog_data["campaign_id"]))
    await notifier.notify_user(
        user,
        payload=MessagePayloadDto(
            i18n_key="ntf-giveaway.buy-instruction",
            i18n_kwargs={
                "plan_name": details.plan_name,
                "duration_days": details.campaign.eligible_duration_days,
            },
        ),
    )
    await dialog_manager.start(
        Subscription.PLAN,
        data={"plan_id": details.campaign.eligible_plan_id},
        mode=StartMode.RESET_STACK,
    )


async def on_client_phone_request(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    await dialog_manager.switch_to(ClientGiveaways.PHONE)


@inject
async def on_client_phone_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    save_phone: FromDishka[SaveGiveawayPhone],
    notifier: FromDishka[Notifier],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    phone = (message.text or "").strip()
    if not phone.isdigit() or not 10 <= len(phone) <= 15:
        await notifier.notify_user(user, i18n_key="ntf-giveaway.phone-invalid")
        return
    entry_id = dialog_manager.dialog_data.get("entry_id")
    if not isinstance(entry_id, int):
        await notifier.notify_user(user, i18n_key="ntf-error.unknown")
        return
    await save_phone(
        user,
        SaveGiveawayPhoneDto(
            entry_id=entry_id,
            user_telegram_id=user.telegram_id,
            phone=phone,
        ),
    )
    await notifier.notify_user(user, i18n_key="ntf-giveaway.phone-saved")
    await dialog_manager.switch_to(ClientGiveaways.VIEW)
