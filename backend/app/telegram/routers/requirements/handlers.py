import asyncio
from typing import Any, Final

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import JOIN_TRANSITION, LEAVE_TRANSITION, ChatMemberUpdatedFilter
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message, Update
from aiogram_dialog import DialogManager, ShowMode, StartMode
from dishka import FromDishka
from fluentogram import TranslatorHub
from loguru import logger
from redis.asyncio import Redis

from app.modules.settings import (
    BotRequirementsDto,
    GetBotRequirementsUseCase,
    ReportBotStatusUseCase,
)
from app.modules.subscriptions import ApplyChannelMembershipUseCase, ChannelMembershipDto
from app.modules.users import UserDto
from app.telegram.i18n import get_translator
from app.telegram.legal_gate import gate_message_key
from app.telegram.middlewares.requirements import (
    CHANNEL_CHECK_CALLBACK,
    ask_requirement,
    channel_keyboard,
    channel_member_key,
    is_channel_member,
)
from app.telegram.states import MainMenu

router = Router(name=__name__)

# keeps the replay tasks referenced until they finish
_replays: Final[set[asyncio.Task[Any]]] = set()


async def _replay(dispatcher: Dispatcher, bot: Bot, message: Message) -> None:
    try:
        await dispatcher.feed_update(bot, Update(update_id=0, message=message))
    except Exception:
        logger.exception(f"Failed to replay the stopped message for chat {message.chat.id}")


async def _resume(
    callback: CallbackQuery,
    user: UserDto,
    dialog_manager: DialogManager,
    redis: Redis,
    dispatcher: Dispatcher,
) -> None:
    if isinstance(callback.message, Message):
        await callback.message.delete()
    # the message a requirement stopped (a /start deep link) goes on where it was headed
    stopped = await redis.getdel(gate_message_key(user.id))
    if stopped is not None and callback.bot is not None:
        # the next requirement, if any, stops it again. A separate task: this
        # callback holds the user's event-isolation lock, the replay waits for it
        task = asyncio.create_task(
            _replay(dispatcher, callback.bot, Message.model_validate_json(stopped))
        )
        _replays.add(task)
        task.add_done_callback(_replays.discard)
        return
    await dialog_manager.start(
        state=MainMenu.MAIN, mode=StartMode.RESET_STACK, show_mode=ShowMode.SEND
    )


async def _is_subscribed(
    callback: CallbackQuery,
    user: UserDto,
    requirements: BotRequirementsDto,
    redis: Redis,
    report: ReportBotStatusUseCase,
) -> bool:
    channel_id = requirements.channel_id
    if (
        not requirements.channel_required
        or channel_id is None
        or user.telegram_id is None
        or callback.bot is None
    ):
        return True
    return await is_channel_member(callback.bot, redis, channel_id, user.telegram_id, report)


async def continue_requirements(
    callback: CallbackQuery,
    user: UserDto,
    dialog_manager: DialogManager,
    requirements: BotRequirementsDto,
    redis: Redis,
    i18n: TranslatorHub,
    report: ReportBotStatusUseCase,
    dispatcher: Dispatcher,
) -> None:
    if not await _is_subscribed(callback, user, requirements, redis, report):
        runner = get_translator(i18n, user)
        if isinstance(callback.message, Message):
            await callback.message.delete()
        await ask_requirement(
            callback, runner.get("ntf-requirements.channel"), channel_keyboard(runner, requirements)
        )
        return
    await callback.answer()
    await _resume(callback, user, dialog_manager, redis, dispatcher)


@router.callback_query(F.data == CHANNEL_CHECK_CALLBACK)
async def on_channel_check(
    callback: CallbackQuery,
    user: UserDto,
    dialog_manager: DialogManager,
    get_requirements: FromDishka[GetBotRequirementsUseCase],
    redis: FromDishka[Redis],
    i18n: FromDishka[TranslatorHub],
    report: FromDishka[ReportBotStatusUseCase],
    dispatcher: Dispatcher,
) -> None:
    requirements = await get_requirements.system()
    if user.telegram_id is not None and requirements.channel_id is not None:
        await redis.delete(channel_member_key(requirements.channel_id, user.telegram_id))
    if not await _is_subscribed(callback, user, requirements, redis, report):
        await callback.answer(
            get_translator(i18n, user).get("ntf-requirements.channel-not-found"),
            show_alert=True,
        )
        return
    await callback.answer()
    await _resume(callback, user, dialog_manager, redis, dispatcher)


async def _on_membership(
    update: ChatMemberUpdated,
    joined: bool,
    bot: Bot,
    apply_channel_membership: ApplyChannelMembershipUseCase,
    get_requirements: GetBotRequirementsUseCase,
    redis: Redis,
    i18n: TranslatorHub,
) -> None:
    telegram_id = update.new_chat_member.user.id
    # the gate must not trust a cached "member" after a leave
    await redis.delete(channel_member_key(update.chat.id, telegram_id))
    user = await apply_channel_membership.system(
        ChannelMembershipDto(telegram_id=telegram_id, chat_id=update.chat.id, joined=joined)
    )
    if user is None:
        return
    runner = get_translator(i18n, user)
    if joined:
        await bot.send_message(telegram_id, runner.get("ntf-requirements.trial-resumed"))
        return
    await bot.send_message(
        telegram_id,
        runner.get("ntf-requirements.trial-paused"),
        reply_markup=channel_keyboard(runner, await get_requirements.system()),
    )


@router.chat_member(ChatMemberUpdatedFilter(LEAVE_TRANSITION))
async def on_channel_leave(
    update: ChatMemberUpdated,
    bot: Bot,
    apply_channel_membership: FromDishka[ApplyChannelMembershipUseCase],
    get_requirements: FromDishka[GetBotRequirementsUseCase],
    redis: FromDishka[Redis],
    i18n: FromDishka[TranslatorHub],
) -> None:
    await _on_membership(
        update, False, bot, apply_channel_membership, get_requirements, redis, i18n
    )


@router.chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def on_channel_join(
    update: ChatMemberUpdated,
    bot: Bot,
    apply_channel_membership: FromDishka[ApplyChannelMembershipUseCase],
    get_requirements: FromDishka[GetBotRequirementsUseCase],
    redis: FromDishka[Redis],
    i18n: FromDishka[TranslatorHub],
) -> None:
    await _on_membership(update, True, bot, apply_channel_membership, get_requirements, redis, i18n)
