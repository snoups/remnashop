from dataclasses import dataclass
from typing import Optional

from loguru import logger

from src.application.common import Interactor
from src.application.common.dao import SettingsDao
from src.application.common.policy import Permission
from src.application.common.uow import UnitOfWork
from src.application.dto import SettingsDto, UserDto
from src.core.types import NotificationType


class ToggleNotification(Interactor[NotificationType, Optional[SettingsDto]]):
    required_permission = Permission.SETTINGS_NOTIFICATIONS

    def __init__(self, uow: UnitOfWork, settings_dao: SettingsDao) -> None:
        self.uow = uow
        self.settings_dao = settings_dao

    async def _execute(
        self, actor: UserDto, notification_type: NotificationType
    ) -> Optional[SettingsDto]:
        async with self.uow:
            settings = await self.settings_dao.get()
            settings.notifications.toggle(notification_type)
            updated = await self.settings_dao.update(settings)

            await self.uow.commit()

        logger.info(f"{actor.log} Toggled notification '{notification_type}'")
        return updated


@dataclass
class UpdateSystemNotifyRouteDto:
    notification_type: NotificationType
    chat_id: int
    thread_id: Optional[int]


class UpdateSystemNotifyRoute(Interactor[UpdateSystemNotifyRouteDto, Optional[SettingsDto]]):
    required_permission = Permission.SETTINGS_NOTIFICATIONS

    def __init__(self, uow: UnitOfWork, settings_dao: SettingsDao) -> None:
        self.uow = uow
        self.settings_dao = settings_dao

    async def _execute(
        self, actor: UserDto, data: UpdateSystemNotifyRouteDto
    ) -> Optional[SettingsDto]:
        async with self.uow:
            settings = await self.settings_dao.get()
            settings.notifications.set_route(data.notification_type, data.chat_id, data.thread_id)
            updated = await self.settings_dao.update(settings)
            await self.uow.commit()

        logger.info(
            f"{actor.log} Updated notify route for '{data.notification_type}': "
            f"chat={data.chat_id}, thread={data.thread_id}"
        )
        return updated


class ClearSystemNotifyRoute(Interactor[NotificationType, Optional[SettingsDto]]):
    required_permission = Permission.SETTINGS_NOTIFICATIONS

    def __init__(self, uow: UnitOfWork, settings_dao: SettingsDao) -> None:
        self.uow = uow
        self.settings_dao = settings_dao

    async def _execute(
        self, actor: UserDto, notification_type: NotificationType
    ) -> Optional[SettingsDto]:
        async with self.uow:
            settings = await self.settings_dao.get()
            settings.notifications.clear_route(notification_type)
            updated = await self.settings_dao.update(settings)
            await self.uow.commit()

        logger.info(f"{actor.log} Cleared notify route for '{notification_type}'")
        return updated
