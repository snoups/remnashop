from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager
from aiogram_dialog.api.exceptions import UnknownIntent, UnknownState
from aiogram_dialog.widgets.kbd import Button
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner
from httpx import AsyncClient
from loguru import logger
from remnawave import RemnawaveSDK

from src.bot.filters import SuperDevFilter
from src.core.config.app import AppConfig
from src.core.utils.formatters import format_user_log as log
from src.infrastructure.database.models.dto import UserDto

router = Router(name=__name__)


@inject
@router.message(Command("test"), SuperDevFilter())
async def on_test_command(
    message: Message, user: UserDto, config: AppConfig, remnawave: FromDishka[RemnawaveSDK]
) -> None:
    logger.info(f"{log(user)} Test command executed")

    async with AsyncClient() as client:
        response = await client.get(
            "https://remna.crackduck.ru/api/users",
            headers={
                "Authorization": f"Bearer {config.remnawave.token.get_secret_value()}",
                "x-forwarded-proto": "https",
                "x-forwarded-for": "127.0.0.1",
            },
            params={"size": "5", "start": "0"},
        )
        logger.success(response.json())
    # remna_user = await remnawave.users.get_user_by_uuid(
    #     UUID("c5f0afd5-e682-41f6-82d9-ade08feba776")
    # )
    # remna_user = await remnawave.users.get_users_by_telegram_id(str(user.telegram_id))
    # logger.critical(remna_user)
    # logger.critical(user.transactions)
    # logger.critical(user.subscriptions)
    # logger.critical(user.promocode_activations)
    # raise UnknownState("test_state")
    # raise UnknownIntent("test_intent")


@inject
async def show_dev_popup(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
) -> None:
    await callback.answer(text=i18n.get("development"), show_alert=True)
