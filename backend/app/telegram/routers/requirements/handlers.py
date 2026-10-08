from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode, StartMode
from dishka import FromDishka
from fluentogram import TranslatorHub
from redis.asyncio import Redis

from app.modules.settings import BotRequirementsDto, GetBotRequirementsUseCase
from app.modules.users import AcceptRulesUseCase, UserDto
from app.telegram.i18n import get_translator
from app.telegram.middlewares.requirements import (
    CHANNEL_CHECK_CALLBACK,
    RULES_ACCEPT_CALLBACK,
    ask_requirement,
    channel_keyboard,
    channel_member_key,
    is_channel_member,
)
from app.telegram.states import MainMenu

router = Router(name=__name__)


async def _open_menu(callback: CallbackQuery, dialog_manager: DialogManager) -> None:
    if isinstance(callback.message, Message):
        await callback.message.delete()
    await dialog_manager.start(
        state=MainMenu.MAIN, mode=StartMode.RESET_STACK, show_mode=ShowMode.SEND
    )


async def _is_subscribed(
    callback: CallbackQuery, user: UserDto, requirements: BotRequirementsDto, redis: Redis
) -> bool:
    channel_id = requirements.channel_id
    if (
        not requirements.channel_required
        or channel_id is None
        or user.telegram_id is None
        or callback.bot is None
    ):
        return True
    return await is_channel_member(callback.bot, redis, channel_id, user.telegram_id)


@router.callback_query(F.data == RULES_ACCEPT_CALLBACK)
async def on_rules_accepted(
    callback: CallbackQuery,
    user: UserDto,
    dialog_manager: DialogManager,
    accept_rules: FromDishka[AcceptRulesUseCase],
    get_requirements: FromDishka[GetBotRequirementsUseCase],
    redis: FromDishka[Redis],
    i18n: FromDishka[TranslatorHub],
) -> None:
    await accept_rules(user)
    requirements = await get_requirements.system()
    if not await _is_subscribed(callback, user, requirements, redis):
        runner = get_translator(i18n, user)
        if isinstance(callback.message, Message):
            await callback.message.delete()
        await ask_requirement(
            callback, runner.get("ntf-requirements.channel"), channel_keyboard(runner, requirements)
        )
        return
    await callback.answer()
    await _open_menu(callback, dialog_manager)


@router.callback_query(F.data == CHANNEL_CHECK_CALLBACK)
async def on_channel_check(
    callback: CallbackQuery,
    user: UserDto,
    dialog_manager: DialogManager,
    get_requirements: FromDishka[GetBotRequirementsUseCase],
    redis: FromDishka[Redis],
    i18n: FromDishka[TranslatorHub],
) -> None:
    requirements = await get_requirements.system()
    if user.telegram_id is not None and requirements.channel_id is not None:
        await redis.delete(channel_member_key(requirements.channel_id, user.telegram_id))
    if not await _is_subscribed(callback, user, requirements, redis):
        await callback.answer(
            get_translator(i18n, user).get("ntf-requirements.channel-not-found"),
            show_alert=True,
        )
        return
    await callback.answer()
    await _open_menu(callback, dialog_manager)
