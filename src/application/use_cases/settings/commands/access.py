from loguru import logger

from src.application.common import Interactor
from src.application.common.dao import SettingsDao, WaitlistDao
from src.application.common.policy import Permission
from src.application.common.uow import UnitOfWork
from src.application.dto import UserDto
from src.core.enums import AccessMode
from src.infrastructure.taskiq.tasks.notifications import notify_payments_restored


class ChangeAccessMode(Interactor[AccessMode, None]):
    required_permission = Permission.SETTINGS_ACCESS

    def __init__(self, uow: UnitOfWork, settings_dao: SettingsDao) -> None:
        self.uow = uow
        self.settings_dao = settings_dao

    async def _execute(self, actor: UserDto, new_mode: AccessMode) -> None:
        async with self.uow:
            settings = await self.settings_dao.get()
            old_mode = settings.access.mode
            settings.access.mode = new_mode
            await self.settings_dao.update(settings)
            await self.uow.commit()

        logger.info(f"{actor.log} Changed access mode from '{old_mode}' to '{new_mode}'")


class TogglePayments(Interactor[None, None]):
    required_permission = Permission.SETTINGS_ACCESS

    def __init__(
        self,
        uow: UnitOfWork,
        settings_dao: SettingsDao,
        waitlist_dao: WaitlistDao,
    ) -> None:
        self.uow = uow
        self.settings_dao = settings_dao
        self.waitlist_dao = waitlist_dao

    async def _execute(self, actor: UserDto, data: None) -> None:
        async with self.uow:
            settings = await self.settings_dao.get()
            new_state = not settings.access.payments_allowed
            settings.access.payments_allowed = new_state
            await self.settings_dao.update(settings)
            await self.uow.commit()

        logger.info(f"{actor.log} Toggled payments availability to '{new_state}'")

        if new_state is True:
            waiting_users = await self.waitlist_dao.get_members()

            if waiting_users:
                logger.info(f"Triggering notification task for '{len(waiting_users)}' users")
                await notify_payments_restored.kiq(waiting_users)  # type: ignore[call-overload]

                await self.waitlist_dao.clear()
                logger.info("Waitlist has been cleared after triggering notifications")


class ToggleRegistration(Interactor[None, None]):
    required_permission = Permission.SETTINGS_ACCESS

    def __init__(self, uow: UnitOfWork, settings_dao: SettingsDao) -> None:
        self.uow = uow
        self.settings_dao = settings_dao

    async def _execute(self, actor: UserDto, data: None) -> None:
        async with self.uow:
            settings = await self.settings_dao.get()
            new_state = not settings.access.registration_allowed
            settings.access.registration_allowed = new_state
            await self.settings_dao.update(settings)
            await self.uow.commit()

        logger.info(f"{actor.log} Toggled registration availability to '{new_state}'")
