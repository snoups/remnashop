from datetime import timedelta
from uuid import UUID

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager
from aiogram_dialog.api.exceptions import UnknownIntent, UnknownState
from aiogram_dialog.widgets.kbd import Button
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner
from loguru import logger
from remnapy import RemnawaveSDK
from remnapy.models import CreateUserRequestDto

from src.bot.filters import SuperDevFilter
from src.core.config.app import AppConfig
from src.core.utils.formatters import format_user_log as log
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import SubscriptionDto, UserDto
from src.infrastructure.database.models.dto.plan import PlanSnapshotDto
from src.services.remnawave import RemnawaveService
from src.services.subscription import SubscriptionService

router = Router(name=__name__)


@inject
@router.message(Command("test"), SuperDevFilter())
async def on_test_command(
    message: Message,
    user: UserDto,
    config: AppConfig,
    remnawave: FromDishka[RemnawaveSDK],
    remnawave_service: FromDishka[RemnawaveService],
    subscription_service: FromDishka[SubscriptionService],
) -> None:
    logger.info(f"{log(user)} Test command executed")

    #

    # created_user = CreateUserRequestDto(
    #     expire_at=datetime_now() - timedelta(days=2), username=user.remna_name, tag="IMPORTED"
    # )
    # await remnawave.users.create_user(created_user)

    #

    # test = SubscriptionDto(
    #     id=-1,
    #     user_remna_id=UUID(),
    #     traffic_limit=1,
    #     device_limit=2,
    #     internal_squads=[],
    #     external_squad=None,
    #     expire_at=datetime_now() - timedelta(days=2),
    #     url="",
    #     plan=PlanSnapshotDto.test(),
    # )
    # await subscription_service.create(user, test)
    # await remnawave_service.create_user(user, subscription=test)


@inject
async def show_dev_popup(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
) -> None:
    await callback.answer(text=i18n.get("development"), show_alert=True)
