from aiogram import Bot
from aiogram.types import CallbackQuery, TelegramObject
from aiogram.types import User as AiogramUser
from aiogram_dialog.utils import remove_intent_id
from fluentogram import TranslatorHub
from loguru import logger
from redis.asyncio import Redis

from src.core.config import AppConfig
from src.core.constants import PURCHASE_PREFIX
from src.core.enums import AccessMode
from src.core.storage.keys import AccessWaitListKey
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import UserDto
from src.infrastructure.redis.repository import RedisRepository
from src.infrastructure.taskiq.tasks.notifications import send_access_opened_notifications_task
from src.infrastructure.taskiq.tasks.redirects import redirect_to_main_menu_task
from src.services.notification import NotificationService
from src.services.referral import ReferralService
from src.services.settings import SettingsService
from src.services.user import UserService

from .base import BaseService


class AccessService(BaseService):
    settings_service: SettingsService
    user_service: UserService
    referral_service: ReferralService

    def __init__(
        self,
        config: AppConfig,
        bot: Bot,
        redis_client: Redis,
        redis_repository: RedisRepository,
        translator_hub: TranslatorHub,
        #
        settings_service: SettingsService,
        user_service: UserService,
        referral_service: ReferralService,
        notification_service: NotificationService,
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.settings_service = settings_service
        self.user_service = user_service
        self.referral_service = referral_service
        self.notification_service = notification_service

    async def is_access_allowed(self, aiogram_user: AiogramUser, event: TelegramObject) -> bool:  # noqa: C901
        user = await self.user_service.get(aiogram_user.id)
        settings = await self.settings_service.get()
        mode = settings.access_mode

        is_purchase_blocked = not settings.purchases_allowed
        is_registration_blocked = not settings.registration_allowed

        if not user:
            if mode == AccessMode.INVITED and await self.referral_service.is_referral_event(
                event, aiogram_user.id
            ):
                logger.info(f"Access allowed for referral event for user '{aiogram_user.id}'")
                return True

            if mode in (AccessMode.INVITED, AccessMode.RESTRICTED) or is_registration_blocked:
                logger.info(f"Access denied for new user '{aiogram_user.id}' (mode: {mode})")

                if is_registration_blocked:
                    i18n_key = "ntf-access-denied-registration"
                elif mode == AccessMode.INVITED:
                    i18n_key = "ntf-access-denied-only-invited"
                else:
                    i18n_key = "ntf-access-denied"

                temp_user = UserDto(
                    telegram_id=aiogram_user.id,
                    name=aiogram_user.full_name,
                    language=aiogram_user.language_code,
                )
                await self.notification_service.notify_user(
                    user=temp_user,
                    payload=MessagePayload(i18n_key=i18n_key),
                )
                return False
            return True

        if user.is_blocked:
            logger.info(f"Access denied for user '{user.telegram_id} '(blocked)")
            return False

        if user.is_privileged:
            logger.info(f"Access allowed for user '{user.telegram_id}' (privileged)")
            return True

        if self._is_purchase_action(event) and is_purchase_blocked:
            logger.info(f"Access denied for user '{user.telegram_id}' (purchase event)")
            await redirect_to_main_menu_task.kiq(user.telegram_id)

            await self.notification_service.notify_user(
                user=user,
                payload=MessagePayload(i18n_key="ntf-access-denied-purchasing"),
            )

            if await self._can_add_to_waitlist(user.telegram_id):
                await self.add_user_to_waitlist(user.telegram_id)

            return False

        if mode == AccessMode.PUBLIC:
            logger.info(f"Access allowed for user '{user.telegram_id}' (mode: PUBLIC)")
            return True

        if mode == AccessMode.RESTRICTED:
            logger.info(f"Access denied for user '{user.telegram_id}' (mode: RESTRICTED)")
            await self.notification_service.notify_user(
                user=user,
                payload=MessagePayload(i18n_key="ntf-access-denied"),
            )
            return False

        if mode == AccessMode.INVITED:
            logger.info(f"Access allowed for user '{user.telegram_id}' (mode: INVITED)")
            return True

        return True

    async def get_available_modes(self) -> list[AccessMode]:
        current = await self.settings_service.get_access_mode()
        available = [mode for mode in AccessMode if mode != current]
        logger.debug(f"Available access modes (excluding current '{current}'): {available}")
        return available

    async def set_mode(self, mode: AccessMode) -> None:
        await self.settings_service.set_access_mode(mode)
        logger.info(f"Access mode changed to '{mode}'")

        if mode in (AccessMode.PUBLIC, AccessMode.INVITED):
            waiting_users = await self.get_all_waiting_users()

            if waiting_users:
                logger.info(f"Notifying '{len(waiting_users)}' waiting users about access opening")
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
        logger.debug(f"Retrieved '{len(users)}' users from access waitlist")
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
