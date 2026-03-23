import asyncio
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode
from aiogram_dialog.widgets.kbd import Button
from aiogram_dialog.widgets.input import MessageInput
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger

from src.application.common import Notifier
from src.application.dto import MediaDescriptorDto, MessagePayloadDto, UserDto
from src.application.use_cases.settings.commands.backup import (
    ToggleBackupEnabled,
    ToggleBackupSendToChat,
    UpdateBackupInterval,
    UpdateBackupIntervalDto,
    UpdateBackupMaxFiles,
    UpdateBackupMaxFilesDto,
)
from src.core.config import AppConfig
from src.core.constants import ASSETS_DIR, USER_KEY
from src.core.enums import MediaType
from src.telegram.states import RemnashopBackup


@inject
async def on_toggle_enabled(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    toggle_backup_enabled: FromDishka[ToggleBackupEnabled],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    await toggle_backup_enabled(user, None)


@inject
async def on_toggle_send_to_chat(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    toggle_backup_send_to_chat: FromDishka[ToggleBackupSendToChat],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    await toggle_backup_send_to_chat(user, None)


@inject
async def on_set_interval(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    await dialog_manager.switch_to(RemnashopBackup.INTERVAL)


@inject
async def on_set_max_files(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    await dialog_manager.switch_to(RemnashopBackup.MAX_FILES)


@inject
async def on_interval_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notifier: FromDishka[Notifier],
    update_backup_interval: FromDishka[UpdateBackupInterval],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    try:
        hours = int(message.text.strip())
        if hours < 1 or hours > 720:
            raise ValueError
    except (ValueError, AttributeError):
        await notifier.notify_user(user, i18n_key="ntf-backup.invalid-interval")
        return

    await update_backup_interval(user, UpdateBackupIntervalDto(interval_hours=hours))
    dialog_manager.show_mode = ShowMode.DELETE_AND_SEND
    await dialog_manager.switch_to(RemnashopBackup.MAIN)


@inject
async def on_max_files_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notifier: FromDishka[Notifier],
    update_backup_max_files: FromDishka[UpdateBackupMaxFiles],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    try:
        count = int(message.text.strip())
        if count < 1 or count > 30:
            raise ValueError
    except (ValueError, AttributeError):
        await notifier.notify_user(user, i18n_key="ntf-backup.invalid-max-files")
        return

    await update_backup_max_files(user, UpdateBackupMaxFilesDto(max_files=count))
    dialog_manager.show_mode = ShowMode.DELETE_AND_SEND
    await dialog_manager.switch_to(RemnashopBackup.MAIN)


@inject
async def on_backup_assets(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    notifier: FromDishka[Notifier],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    await notifier.notify_user(user, i18n_key="ntf-backup.assets-started")

    tmp_dir = Path(tempfile.mkdtemp())
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_path = tmp_dir / f"assets_backup_{timestamp}"

        await asyncio.to_thread(
            shutil.make_archive,
            str(zip_path),
            "zip",
            str(ASSETS_DIR.parent),
            str(ASSETS_DIR.name),
        )
        zip_file = Path(str(zip_path) + ".zip")

        await notifier.notify_user(
            user=user,
            payload=MessagePayloadDto(
                i18n_key="",
                media=MediaDescriptorDto(
                    kind="fs",
                    value=str(zip_file),
                    filename=zip_file.name,
                ),
                media_type=MediaType.DOCUMENT,
                delete_after=None,
                disable_default_markup=False,
            ),
        )
        logger.info(f"{user.log} Assets backup sent: {zip_file.name}")
    except Exception as e:
        logger.exception(f"{user.log} Failed to create assets backup: {e}")
        await notifier.notify_user(user, i18n_key="ntf-backup.error")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@inject
async def on_backup_database(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    notifier: FromDishka[Notifier],
    config: FromDishka[AppConfig],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    await notifier.notify_user(user, i18n_key="ntf-backup.db-started")

    tmp_dir = Path(tempfile.mkdtemp())
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dump_file = tmp_dir / f"db_backup_{timestamp}.sql"
        db = config.database

        proc = await asyncio.create_subprocess_exec(
            "pg_dump",
            "-h", db.host,
            "-p", str(db.port),
            "-U", db.user,
            "-d", db.name,
            "-f", str(dump_file),
            env={**__import__("os").environ, "PGPASSWORD": db.password.get_secret_value()},
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"pg_dump failed: {stderr.decode()}")

        await notifier.notify_user(
            user=user,
            payload=MessagePayloadDto(
                i18n_key="",
                media=MediaDescriptorDto(
                    kind="fs",
                    value=str(dump_file),
                    filename=dump_file.name,
                ),
                media_type=MediaType.DOCUMENT,
                delete_after=None,
                disable_default_markup=False,
            ),
        )
        logger.info(f"{user.log} Database backup sent: {dump_file.name}")
    except Exception as e:
        logger.exception(f"{user.log} Failed to create database backup: {e}")
        await notifier.notify_user(user, i18n_key="ntf-backup.error")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
