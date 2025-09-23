from aiogram.types import TelegramObject
from aiogram_dialog.utils import remove_intent_id
from loguru import logger

from src.core.enums import MaintenanceMode
from src.core.storage_keys import MaintenanceModeKey, MaintenanceWaitListKey
from src.core.utils.formatters import format_log_user
from src.infrastructure.database.models.dto import UserDto

from .base import BaseService


class MaintenanceService(BaseService):
    async def is_access_allowed(self, user: UserDto, event: TelegramObject) -> bool:
        if not await self.is_active():
            logger.debug(f"{format_log_user(user)} Access allowed (maintenance not active)")
            return True

        if user.is_privileged:
            logger.debug(f"{format_log_user(user)} Access allowed (privileged user)")
            return True

        if await self.is_global_mode():
            logger.info(f"{format_log_user(user)} Access denied (global maintenance mode)")
            return False

        if await self.is_purchase_mode() and self._is_purchase_action(event):
            logger.info(f"{format_log_user(user)} Access denied (purchase maintenance mode)")

            if await self._can_add_to_waitlist(user.telegram_id):
                await self.add_user_to_waitlist(user.telegram_id)
            return False

        logger.debug(f"{format_log_user(user)} Access allowed (no specific denial condition met)")
        return True

    async def get_current_mode(self) -> MaintenanceMode:
        return await self.redis_repository.get(  # type: ignore[return-value]
            key=MaintenanceModeKey(),
            validator=MaintenanceMode,
            default=MaintenanceMode.OFF,
        )

    async def get_available_modes(self) -> list[MaintenanceMode]:
        current = await self.get_current_mode()
        return [mode for mode in MaintenanceMode if mode != current]

    async def set_mode(self, mode: MaintenanceMode) -> None:
        await self.redis_repository.set(key=MaintenanceModeKey(), value=mode)

    async def is_active(self) -> bool:
        return await self.get_current_mode() != MaintenanceMode.OFF

    async def is_purchase_mode(self) -> bool:
        return await self.get_current_mode() == MaintenanceMode.PURCHASE

    async def is_global_mode(self) -> bool:
        return await self.get_current_mode() == MaintenanceMode.GLOBAL

    async def add_user_to_waitlist(self, telegram_id: int) -> bool:
        added_count = await self.redis_repository.collection_add(
            MaintenanceWaitListKey(),
            telegram_id,
        )

        if added_count > 0:
            logger.info(f"User '{telegram_id}' added to waiting list")
            return True

        logger.debug(f"User '{telegram_id}' is already in the waiting list")
        return False

    async def remove_user_from_waitlist(self, telegram_id: int) -> bool:
        removed_count = await self.redis_repository.collection_remove(
            MaintenanceWaitListKey(),
            telegram_id,
        )

        if removed_count > 0:
            logger.info(f"User '{telegram_id}' removed from waiting list")
            return True

        logger.debug(f"User '{telegram_id}' not found in waiting list")
        return False

    async def get_all_waiting_users(self) -> list[int]:
        members_str = await self.redis_repository.collection_members(key=MaintenanceWaitListKey())
        waiting_users = [int(member) for member in members_str]
        logger.debug(f"Retrieved '{len(waiting_users)}' users from waiting list")
        return waiting_users

    async def clear_all_waiting_users(self) -> None:
        await self.redis_repository.delete(key=MaintenanceWaitListKey())
        logger.info("User waiting list completely cleared")

    async def _can_add_to_waitlist(self, telegram_id: int) -> bool:
        is_member = await self.redis_repository.collection_is_member(
            key=MaintenanceWaitListKey(),
            value=telegram_id,
        )

        if is_member:
            logger.debug(f"User '{telegram_id}' is already on the waiting list")
            return False

        logger.debug(f"User '{telegram_id}' should be added to the waiting list")
        return True

    def _is_purchase_action(self, event: TelegramObject) -> bool:
        # TODO: Find purchase action
        # callback_data = remove_intent_id(event.data)
        return False  # Placeholder
