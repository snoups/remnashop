from aiogram import Bot
from aiogram.types import CallbackQuery, TelegramObject
from aiogram_dialog.utils import remove_intent_id
from fluentogram import TranslatorHub
from loguru import logger
from redis.asyncio import Redis

from src.core.config.app import AppConfig
from src.core.constants import PURCHASE_PREFIX
from src.core.enums import AccessMode
from src.core.storage.keys import AccessWaitListKey
from src.core.utils.formatters import format_user_log as log
from src.infrastructure.database.models.dto import UserDto
from src.infrastructure.redis.repository import RedisRepository
from src.infrastructure.taskiq.tasks.notifications import (
    send_access_denied_notification_task,
    send_access_opened_notifications_task,
)
from src.services.settings import SettingsService

from .base import BaseService


class AccessService(BaseService):
    settings_service: SettingsService

    def __init__(
        self,
        config: AppConfig,
        bot: Bot,
        redis_client: Redis,
        redis_repository: RedisRepository,
        translator_hub: TranslatorHub,
        #
        settings_service: SettingsService,
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.settings_service = settings_service

    async def is_access_allowed(self, user: UserDto, event: TelegramObject) -> bool:
        if user.is_blocked:
            logger.info(f"{log(user)} Access denied (user blocked)")
            return False

        mode = await self.settings_service.get_access_mode()

        if mode == AccessMode.ALL:
            logger.info(f"{log(user)} Access allowed (mode: ALL)")
            return True

        if user.is_privileged:
            logger.info(f"{log(user)} Access allowed (privileged user)")
            return True

        match mode:
            case AccessMode.BLOCKED:
                logger.info(f"{log(user)} Access denied (mode: BLOCKED)")
                await send_access_denied_notification_task.kiq(
                    user=user,
                    i18n_key="ntf-access-denied",
                )
                return False

            case AccessMode.PURCHASE:
                if self._is_purchase_action(event):
                    logger.info(f"{log(user)} Access denied (purchase event)")
                    await send_access_denied_notification_task.kiq(
                        user=user,
                        i18n_key="ntf-access-denied-purchasing",
                    )

                    if await self._can_add_to_waitlist(user.telegram_id):
                        await self.add_user_to_waitlist(user.telegram_id)

                    return False

                logger.info(f"{log(user)} Access allowed (mode: PURCHASE, non-purchase event)")
                return True

            case AccessMode.INVITED:
                invited = await self.is_invited(user)

                if invited:
                    logger.info(f"{log(user)} Access allowed (mode: INVITED)")
                    return True

                logger.info(f"{log(user)} Access denied (not invited)")
                return False

            case _:
                logger.warning(f"{log(user)} Unknown access mode '{mode}'")
                return False

    async def is_invited(self, user: UserDto) -> bool:
        result = True  # TODO: Replace with actual referral check
        logger.debug(f"is_invited check for user '{user.telegram_id}': {result}")
        return result

    async def get_available_modes(self) -> list[AccessMode]:
        current = await self.settings_service.get_access_mode()
        available = [mode for mode in AccessMode if mode != current]
        logger.debug(f"Available access modes (excluding current '{current}'): {available}")
        return available

    async def set_mode(self, mode: AccessMode) -> None:
        await self.settings_service.set_access_mode(mode)
        logger.info(f"Access mode changed to '{mode}'")

        if mode in (AccessMode.ALL, AccessMode.INVITED):
            waiting_users = await self.get_all_waiting_users()

            if waiting_users:
                logger.info(f"Notifying {len(waiting_users)} waiting users about access opening")
                await send_access_opened_notifications_task.kiq(waiting_users)

        await self.clear_all_waiting_users()

    async def add_user_to_waitlist(self, telegram_id: int) -> bool:
        added_count = await self.redis_repository.collection_add(AccessWaitListKey(), telegram_id)

        if added_count > 0:
            logger.info(f"User '{telegram_id}' added to access waitlist")
            return True

        logger.debug(f"User '{telegram_id}' already in access waitlist")
        return False

    async def remove_user_from_waitlist(self, telegram_id: int) -> bool:
        removed_count = await self.redis_repository.collection_remove(
            AccessWaitListKey(),
            telegram_id,
        )

        if removed_count > 0:
            logger.info(f"User '{telegram_id}' removed from access waitlist")
            return True

        logger.debug(f"User '{telegram_id}' not found in access waitlist")
        return False

    async def get_all_waiting_users(self) -> list[int]:
        members_str = await self.redis_repository.collection_members(key=AccessWaitListKey())
        users = [int(member) for member in members_str]
        logger.debug(f"Retrieved {len(users)} users from access waitlist")
        return users

    async def clear_all_waiting_users(self) -> None:
        await self.redis_repository.delete(key=AccessWaitListKey())
        logger.info("Access waitlist completely cleared")

    async def _can_add_to_waitlist(self, telegram_id: int) -> bool:
        is_member = await self.redis_repository.collection_is_member(
            key=AccessWaitListKey(),
            value=telegram_id,
        )

        if is_member:
            logger.debug(f"User '{telegram_id}' already in access waitlist")
            return False

        logger.debug(f"User '{telegram_id}' can be added to access waitlist")
        return True

    def _is_purchase_action(self, event: TelegramObject) -> bool:
        if not isinstance(event, CallbackQuery) or not event.data:
            return False

        callback_data = remove_intent_id(event.data)
        if callback_data[-1].startswith(PURCHASE_PREFIX):
            logger.debug(f"Detected purchase action: {callback_data}")
            return True

        return False
