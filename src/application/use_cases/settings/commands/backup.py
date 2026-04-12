from typing import Optional

from loguru import logger

from src.application.common import Interactor
from src.application.common.dao import SettingsDao
from src.application.common.policy import Permission
from src.application.common.uow import UnitOfWork
from src.application.dto import SettingsDto, UserDto


class ToggleBackupEnabled(Interactor[None, Optional[SettingsDto]]):
    required_permission = Permission.SETTINGS_BACKUP

    def __init__(self, uow: UnitOfWork, settings_dao: SettingsDao) -> None:
        self.uow = uow
        self.settings_dao = settings_dao

    async def _execute(self, actor: UserDto, data: None) -> Optional[SettingsDto]:
        async with self.uow:
            settings = await self.settings_dao.get()
            settings.backup.enabled = not settings.backup.enabled
            updated = await self.settings_dao.update(settings)
            await self.uow.commit()

        logger.info(f"{actor.log} Toggled backup enabled: {settings.backup.enabled}")
        return updated


class ToggleBackupSendToChat(Interactor[None, Optional[SettingsDto]]):
    required_permission = Permission.SETTINGS_BACKUP

    def __init__(self, uow: UnitOfWork, settings_dao: SettingsDao) -> None:
        self.uow = uow
        self.settings_dao = settings_dao

    async def _execute(self, actor: UserDto, data: None) -> Optional[SettingsDto]:
        async with self.uow:
            settings = await self.settings_dao.get()
            settings.backup.send_to_chat = not settings.backup.send_to_chat
            updated = await self.settings_dao.update(settings)
            await self.uow.commit()

        logger.info(f"{actor.log} Toggled backup send_to_chat: {settings.backup.send_to_chat}")
        return updated


BACKUP_INTERVAL_MIN = 1
BACKUP_INTERVAL_MAX = 720


class UpdateBackupInterval(Interactor[str, Optional[SettingsDto]]):
    required_permission = Permission.SETTINGS_BACKUP

    def __init__(self, uow: UnitOfWork, settings_dao: SettingsDao) -> None:
        self.uow = uow
        self.settings_dao = settings_dao

    async def _execute(
        self,
        actor: UserDto,
        input_interval_hours: str,
    ) -> Optional[SettingsDto]:
        interval_hours = int(input_interval_hours.strip())
        if interval_hours < BACKUP_INTERVAL_MIN or interval_hours > BACKUP_INTERVAL_MAX:
            raise ValueError

        async with self.uow:
            settings = await self.settings_dao.get()
            settings.backup.interval_hours = interval_hours
            updated = await self.settings_dao.update(settings)
            await self.uow.commit()

        logger.info(f"{actor.log} Set backup interval: {interval_hours}h")
        return updated


BACKUP_MAX_FILES_MIN = 1
BACKUP_MAX_FILES_MAX = 30


class UpdateBackupMaxFiles(Interactor[str, Optional[SettingsDto]]):
    required_permission = Permission.SETTINGS_BACKUP

    def __init__(self, uow: UnitOfWork, settings_dao: SettingsDao) -> None:
        self.uow = uow
        self.settings_dao = settings_dao

    async def _execute(
        self,
        actor: UserDto,
        input_max_files: str,
    ) -> Optional[SettingsDto]:
        max_files = int(input_max_files.strip())
        if max_files < BACKUP_MAX_FILES_MIN or max_files > BACKUP_MAX_FILES_MAX:
            raise ValueError

        async with self.uow:
            settings = await self.settings_dao.get()
            settings.backup.max_files = max_files
            updated = await self.settings_dao.update(settings)
            await self.uow.commit()

        logger.info(f"{actor.log} Set backup max_files: {max_files}")
        return updated
