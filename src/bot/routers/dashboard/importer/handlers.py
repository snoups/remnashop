from pathlib import Path

from aiogram import Bot
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger
from remnapy import RemnawaveSDK

from src.bot.states import DashboardImporter
from src.core.constants import USER_KEY
from src.core.storage.keys import SyncRunningKey
from src.core.utils.formatters import format_user_log as log
from src.core.utils.message_payload import MessagePayload
from src.core.utils.validators import is_double_click
from src.infrastructure.database.models.dto import UserDto
from src.infrastructure.redis.repository import RedisRepository
from src.infrastructure.taskiq.tasks.importer import (
    import_exported_users_task,
    sync_all_users_from_panel_task,
)
from src.services.importer import ImporterService
from src.services.notification import NotificationService


@inject
async def on_import_from_bot(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(i18n_key="ntf-importer-not-support"),
    )


@inject
async def on_database_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    bot: FromDishka[Bot],
    notification_service: FromDishka[NotificationService],
    importer_service: FromDishka[ImporterService],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.debug(f"{log(user)} Processing database upload")

    document = message.document
    if not document:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-importer-not-file"),
        )
        return

    local_file_path = Path(f"/tmp/{document.file_name}")
    file = await bot.get_file(document.file_id)

    if not file.file_path:
        raise ValueError(f"File path not found for document '{document.file_name}'")
        return

    await bot.download_file(file.file_path, destination=local_file_path)
    logger.info(f"{log(user)} Received file: '{local_file_path}'")

    try:
        users = importer_service.get_users_from_xui(local_file_path)
    except Exception as exception:
        logger.exception(f"Failed to parse users: {exception}")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-importer-db-failed"),
        )
        return

    if not users:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-importer-exported-users-empty"),
        )
        return

    active, expired = importer_service.split_active_and_expired(users)

    dialog_manager.dialog_data["users"] = {
        "all": users,
        "active": active,
        "expired": expired,
    }


@inject
async def on_squads(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    remnawave: FromDishka[RemnawaveSDK],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    result = await remnawave.internal_squads.get_internal_squads()

    if not result.internal_squads:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-squads-empty"),
        )
        return

    await dialog_manager.switch_to(state=DashboardImporter.SQUADS)


@inject
async def on_squad_select(
    callback: CallbackQuery,
    widget: Select[str],
    dialog_manager: DialogManager,
    selected_squad: str,
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    selected_squads: list = dialog_manager.dialog_data.get("selected_squads", [])

    if selected_squad in selected_squads:
        selected_squads.remove(selected_squad)
        logger.info(f"{log(user)} Unset squad '{selected_squad}'")
    else:
        selected_squads.append(selected_squad)
        logger.info(f"{log(user)} Set squad '{selected_squad}'")

    dialog_manager.dialog_data["selected_squads"] = selected_squads


@inject
async def on_import_all_xui(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    users = dialog_manager.dialog_data["users"]
    selected_squads = dialog_manager.dialog_data.get("selected_squads", [])

    if not selected_squads:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-importer-internal-squads-empty"),
        )
        return

    dialog_manager.dialog_data["has_started"] = True
    notification = await notification_service.notify_user(
        user=user,
        payload=MessagePayload.not_deleted(i18n_key="ntf-importer-import-started"),
    )

    task = await import_exported_users_task.kiq(users["all"], selected_squads)

    logger.info(f"{log(user)} Started import '{len(users['all'])}' users")
    result = await task.wait_result()
    success_count, failed_count = result.return_value

    if notification:
        await notification.delete()

    dialog_manager.dialog_data["completed"] = {
        "total_count": len(users["all"]),
        "success_count": success_count,
        "failed_count": failed_count,
    }
    await dialog_manager.switch_to(state=DashboardImporter.IMPORT_COMPLETED)


@inject
async def on_import_active_xui(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    users = dialog_manager.dialog_data["users"]
    selected_squads = dialog_manager.dialog_data.get("selected_squads", [])

    if not selected_squads:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-importer-internal-squads-empty"),
        )
        return

    dialog_manager.dialog_data["has_started"] = True
    notification = await notification_service.notify_user(
        user=user,
        payload=MessagePayload.not_deleted(i18n_key="ntf-importer-import-started"),
    )

    task = await import_exported_users_task.kiq(users["active"], selected_squads)
    logger.info(f"{log(user)} Started import '{len(users['active'])}' users")
    result = await task.wait_result()
    success_count, failed_count = result.return_value

    if notification:
        await notification.delete()

    dialog_manager.dialog_data["completed"] = {
        "total_count": len(users["active"]),
        "success_count": success_count,
        "failed_count": failed_count,
    }
    await dialog_manager.switch_to(state=DashboardImporter.IMPORT_COMPLETED)


@inject
async def on_sync(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    redis_repository: FromDishka[RedisRepository],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    selected_bot = callback.data
    dialog_manager.dialog_data["selected_bot"] = selected_bot
    key = SyncRunningKey()

    if await redis_repository.get(key, str, False):
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-importer-sync-already-running"),
        )
        return

    if is_double_click(
        dialog_manager,
        key="sync_confirm",
        cooldown=10,
    ):
        await redis_repository.set(key, value=True, ex=3600)

        notification = await notification_service.notify_user(
            user=user,
            payload=MessagePayload.not_deleted(i18n_key="ntf-importer-sync-started"),
        )

        task = await sync_all_users_from_panel_task.kiq()
        result = await task.wait_result()
        result = result.return_value

        if not result:
            await notification_service.notify_user(
                user=user,
                payload=MessagePayload(i18n_key="ntf-importer-users-not-found"),
            )
            return

        dialog_manager.dialog_data["completed"] = result

        if notification:
            await notification.delete()

        await dialog_manager.switch_to(state=DashboardImporter.SYNC_COMPLETED)
        return

    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(i18n_key="ntf-double-click-confirm"),
    )
