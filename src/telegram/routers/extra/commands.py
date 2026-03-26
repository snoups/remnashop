from aiogram import Router
from aiogram.filters import Command as FilterCommand
from aiogram.types import Message
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger

from src.application.common import Notifier, TranslatorRunner
from src.application.common.dao import SettingsDao
from src.application.dto import MessagePayloadDto, UserDto
from src.application.services import BotService
from src.core.enums import Command
from src.telegram.keyboards import get_contact_support_keyboard

router = Router(name=__name__)


@inject
@router.message(FilterCommand(Command.PAYSUPPORT.value.command))
async def on_paysupport_command(
    message: Message,
    user: UserDto,
    bot_service: FromDishka[BotService],
    i18n: FromDishka[TranslatorRunner],
    notifier: FromDishka[Notifier],
) -> None:
    logger.info(f"{user.log} Called '/paysupport' command")
    support_url = bot_service.get_support_url(text=i18n.get("message.paysupport"))

    await notifier.notify_user(
        user=user,
        payload=MessagePayloadDto(
            i18n_key="ntf-command.paysupport",
            reply_markup=get_contact_support_keyboard(support_url),
            disable_default_markup=False,
            delete_after=None,
        ),
    )


@inject
@router.message(FilterCommand(Command.RULES.value.command))
async def on_rules_command(
    message: Message,
    user: UserDto,
    notifier: FromDishka[Notifier],
    settings_dao: FromDishka[SettingsDao],
) -> None:
    logger.info(f"{user.log} Called '/rules' command")

    settings = await settings_dao.get()
    await notifier.notify_user(
        user=user,
        payload=MessagePayloadDto(
            i18n_key="ntf-command.rules",
            i18n_kwargs={"url": settings.requirements.rules_url},
            disable_default_markup=False,
            delete_after=None,
        ),
    )


@inject
@router.message(FilterCommand(Command.HELP.value.command))
async def on_help_command(
    message: Message,
    user: UserDto,
    bot_service: FromDishka[BotService],
    i18n: FromDishka[TranslatorRunner],
    notifier: FromDishka[Notifier],
) -> None:
    logger.info(f"{user.log} Called '/help' command")
    support_url = bot_service.get_support_url(text=i18n.get("message.help"))

    await notifier.notify_user(
        user=user,
        payload=MessagePayloadDto(
            i18n_key="ntf-command.help",
            reply_markup=get_contact_support_keyboard(support_url),
            disable_default_markup=False,
            delete_after=None,
        ),
    )
