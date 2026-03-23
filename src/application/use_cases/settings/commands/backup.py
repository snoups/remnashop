from dataclasses import dataclass
from typing import Optional

from loguru import logger

from src.application.common import Interactor
from src.application.common.dao import SettingsDao
from src.application.common.policy import Permission
from src.application.common.uow import UnitOfWork
from src.application.dto import SettingsDto, UserDto


class ToggleBackupEnabled(Interactor[None, Optional[SettingsDto]]):
    required_permission = Permission.VIEW_BACKUP

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
    required_permission = Permission.VIEW_BACKUP

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


@dataclass(frozen=True)
class UpdateBackupIntervalDto:
    interval_hours: int


class UpdateBackupInterval(Interactor[UpdateBackupIntervalDto, Optional[SettingsDto]]):
    required_permission = Permission.VIEW_BACKUP

    def __init__(self, uow: UnitOfWork, settings_dao: SettingsDao) -> None:
        self.uow = uow
        self.settings_dao = settings_dao

    async def _execute(self, actor: UserDto, data: UpdateBackupIntervalDto) -> Optional[SettingsDto]:
        async with self.uow:
            settings = await self.settings_dao.get()
            settings.backup.interval_hours = data.interval_hours
            updated = await self.settings_dao.update(settings)
            await self.uow.commit()

        logger.info(f"{actor.log} Set backup interval: {data.interval_hours}h")
        return updated


@dataclass(frozen=True)
class UpdateBackupMaxFilesDto:
    max_files: int


class UpdateBackupMaxFiles(Interactor[UpdateBackupMaxFilesDto, Optional[SettingsDto]]):
    required_permission = Permission.VIEW_BACKUP

    def __init__(self, uow: UnitOfWork, settings_dao: SettingsDao) -> None:
        self.uow = uow
        self.settings_dao = settings_dao

    async def _execute(self, actor: UserDto, data: UpdateBackupMaxFilesDto) -> Optional[SettingsDto]:
        async with self.uow:
            settings = await self.settings_dao.get()
            settings.backup.max_files = data.max_files
            updated = await self.settings_dao.update(settings)
            await self.uow.commit()

        logger.info(f"{actor.log} Set backup max_files: {data.max_files}")
        return updated
