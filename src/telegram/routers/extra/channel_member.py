from aiogram import Router
from aiogram.filters import JOIN_TRANSITION, LEAVE_TRANSITION, ChatMemberUpdatedFilter
from aiogram.types import ChatMemberUpdated
from dishka import FromDishka

from src.application.common import Notifier
from src.application.common.dao import SettingsDao
from src.application.dto import MessagePayloadDto
from src.application.use_cases.subscription import (
    ChannelMemberEventDto,
    DisableTrialSubscription,
    EnableTrialSubscription,
)
from src.telegram.keyboards import CALLBACK_CHANNEL_CONFIRM, get_channel_keyboard

router = Router(name=__name__)


@router.chat_member(ChatMemberUpdatedFilter(LEAVE_TRANSITION))
async def on_channel_leave(
    member: ChatMemberUpdated,
    disable_trial: FromDishka[DisableTrialSubscription],
    notifier: FromDishka[Notifier],
    settings_dao: FromDishka[SettingsDao],
) -> None:
    event = ChannelMemberEventDto(
        telegram_id=member.new_chat_member.user.id,
        chat_id=member.chat.id,
        chat_username=member.chat.username,
    )
    user = await disable_trial.system(event)

    if user is None:
        return

    settings = await settings_dao.get()
    await notifier.notify_user(
        user=user,
        payload=MessagePayloadDto(
            i18n_key="ntf-requirement.trial-paused",
            reply_markup=get_channel_keyboard(settings.requirements.channel_url),
            disable_default_markup=True,
            delete_after=None,
        ),
    )


@router.chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def on_channel_join(
    member: ChatMemberUpdated,
    enable_trial: FromDishka[EnableTrialSubscription],
    notifier: FromDishka[Notifier],
) -> None:
    event = ChannelMemberEventDto(
        telegram_id=member.new_chat_member.user.id,
        chat_id=member.chat.id,
        chat_username=member.chat.username,
    )
    user = await enable_trial.system(event)

    if user is None:
        return

    await notifier.notify_user(
        user=user,
        payload=MessagePayloadDto(
            i18n_key="ntf-requirement.trial-restored",
            disable_default_markup=True,
            delete_after=None,
        ),
    )
