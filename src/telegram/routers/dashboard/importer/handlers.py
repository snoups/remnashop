from adaptix import Retort
from aiogram import Bot
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger
from redis.asyncio import Redis
from remnapy import RemnawaveSDK

from src.application.common import Notifier
from src.application.dto import MessagePayloadDto, UserDto
from src.application.use_cases.importer.commands.processing import ProcessImportFile
from src.core.constants import USER_KEY
from src.infrastructure.redis.keys import ImportRunningKey, SyncRunningKey
from src.infrastructure.taskiq.tasks.importer import (
    import_exported_users_task,
    sync_all_users_from_panel_task,
)
from src.telegram.states import DashboardImporter
from src.telegram.utils import is_double_click


@inject
async def on_database_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    bot: FromDishka[Bot],
    notifier: FromDishka[Notifier],
    process_import_file: FromDishka[ProcessImportFile],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.debug(f"{user.log} Processing database upload")

    document = message.document
    if not document:
        await notifier.notify_user(user, i18n_key="ntf-importer.not-file")
        return

    try:
        result = await process_import_file(user, document)
    except Exception as exception:
        logger.exception(f"Failed to process database: {exception}")
        await notifier.notify_user(user, i18n_key="ntf-importer.db-failed")
        return

    if not result.all_users:
        await notifier.notify_user(user, i18n_key="ntf-importer.users-empty")
        return

    dialog_manager.dialog_data["users"] = {
        "all": result.all_users,
        "active": result.active_users,
        "expired": result.expired_users,
    }

    logger.info(f"{user.log} Successfully parsed '{len(result.all_users)}' users from file")


@inject
async def on_squads(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    remnawave_sdk: FromDishka[RemnawaveSDK],
    notifier: FromDishka[Notifier],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    result = await remnawave_sdk.internal_squads.get_internal_squads()

    if not result.internal_squads:
        await notifier.notify_user(user, i18n_key="ntf-common.squads-empty")
        return

    await dialog_manager.switch_to(state=DashboardImporter.SQUADS)


@inject
async def on_squad_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_squad: str,
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    selected_squads: list = dialog_manager.dialog_data.get("selected_squads", [])

    if selected_squad in selected_squads:
        selected_squads.remove(selected_squad)
        logger.info(f"{user.log} Unset squad '{selected_squad}'")
    else:
        selected_squads.append(selected_squad)
        logger.info(f"{user.log} Set squad '{selected_squad}'")

    dialog_manager.dialog_data["selected_squads"] = selected_squads


@inject
async def on_import_all_xui(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    notifier: FromDishka[Notifier],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    users = dialog_manager.dialog_data["users"]
    selected_squads = dialog_manager.dialog_data.get("selected_squads", [])

    if not selected_squads:
        await notifier.notify_user(user, i18n_key="ntf-common.internal-squads-empty")
        return

    dialog_manager.dialog_data["has_started"] = True
    notification = await notifier.notify_user(
        user,
        payload=MessagePayloadDto(i18n_key="ntf-importer.import-started", delete_after=None),
    )

    task = await import_exported_users_task.kiq(users["all"], selected_squads)  # type: ignore[call-overload]

    logger.info(f"{user.log} Started import '{len(users['all'])}' users")
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
    retort: FromDishka[Retort],
    redis: FromDishka[Redis],
    notifier: FromDishka[Notifier],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    users = dialog_manager.dialog_data["users"]
    selected_squads = dialog_manager.dialog_data.get("selected_squads", [])

    key = retort.dump(ImportRunningKey())

    if await redis.get(key):
        await notifier.notify_user(user, i18n_key="ntf-importer.already-running")
        return

    await redis.set(key, 1, ex=3600)

    if not selected_squads:
        await notifier.notify_user(user, i18n_key="ntf-common.internal-squads-empty")
        return

    dialog_manager.dialog_data["has_started"] = True
    notification = await notifier.notify_user(
        user,
        payload=MessagePayloadDto(i18n_key="ntf-importer.started", delete_after=None),
    )

    task = await import_exported_users_task.kiq(users["active"], selected_squads)  # type: ignore[call-overload]
    logger.info(f"{user.log} Started import '{len(users['active'])}' users")
    result = await task.wait_result()
    success_count, failed_count = result.return_value

    if notification:
        await notification.delete()

    dialog_manager.dialog_data["completed"] = {
        "total_count": len(users["active"]),
        "success_count": success_count,
        "failed_count": failed_count,
    }

    await redis.delete(key)
    await dialog_manager.switch_to(state=DashboardImporter.IMPORT_COMPLETED)


@inject
async def on_sync(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    retort: FromDishka[Retort],
    redis: FromDishka[Redis],
    notifier: FromDishka[Notifier],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    # TODO: before check squads subscription_dao.get_all_active_internal_squads()
    key = retort.dump(SyncRunningKey())

    if await redis.get(key):
        await notifier.notify_user(user, i18n_key="ntf-sync.already-running")
        return

    if is_double_click(
        dialog_manager,
        key="sync_confirm",
        cooldown=10,
    ):
        await redis.set(key, value=1, ex=3600)

        notification = await notifier.notify_user(
            user,
            payload=MessagePayloadDto(i18n_key="ntf-sync.started", delete_after=None),
        )

        task = await sync_all_users_from_panel_task.kiq()  # type: ignore[call-overload]
        result = await task.wait_result()
        result = result.return_value

        if not result:
            await notifier.notify_user(user, i18n_key="ntf-sync.users-not-found")
            return

        dialog_manager.dialog_data["completed"] = result

        if notification:
            await notification.delete()

        await dialog_manager.switch_to(state=DashboardImporter.SYNC_COMPLETED)
        return

    await notifier.notify_user(user, i18n_key="ntf-common.double-click-confirm")
