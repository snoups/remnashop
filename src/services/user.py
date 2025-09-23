from typing import Optional

from aiogram import Bot
from aiogram.types import Message
from aiogram.types import User as AiogramUser
from fluentogram import TranslatorHub
from loguru import logger
from redis.asyncio import Redis

from src.core.config import AppConfig
from src.core.constants import (
    RECENT_ACTIVITY_MAX_COUNT,
    RECENT_REGISTERED_MAX_COUNT,
    TIME_1M,
    TIME_10M,
)
from src.core.enums import Locale, UserRole
from src.core.storage_keys import RecentActivityUsersKey, RecentRegisteredUsersKey
from src.core.utils.key_builder import StorageKey, build_key
from src.infrastructure.database import UnitOfWork
from src.infrastructure.database.models.dto import UserDto
from src.infrastructure.database.models.sql import User
from src.infrastructure.redis import RedisRepository, redis_cache

from .base import BaseService


class UserService(BaseService):
    uow: UnitOfWork

    def __init__(
        self,
        config: AppConfig,
        bot: Bot,
        redis_client: Redis,
        redis_repository: RedisRepository,
        translator_hub: TranslatorHub,
        #
        uow: UnitOfWork,
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.uow = uow

    async def create(self, aiogram_user: AiogramUser) -> UserDto:
        user = UserDto(
            telegram_id=aiogram_user.id,
            username=aiogram_user.username,
            name=aiogram_user.full_name,
            role=(UserRole.DEV if self.config.bot.dev_id == aiogram_user.id else UserRole.USER),
            language=(
                aiogram_user.language_code
                if aiogram_user.language_code in self.config.locales
                else self.config.default_locale
            ),
        )
        db_user = User(**user.model_dump())
        db_created_user = await self.uow.repository.users.create(db_user)

        await self.add_to_recent_registered(user.telegram_id)
        await self._clear_user_cache(user.telegram_id)

        return UserDto.from_model(db_created_user)  # type: ignore[return-value]

    @redis_cache(prefix="get_user", ttl=TIME_1M)
    async def get(self, telegram_id: int) -> Optional[UserDto]:
        db_user = await self.uow.repository.users.get(telegram_id)
        return UserDto.from_model(db_user)

    async def update(self, user: UserDto) -> Optional[UserDto]:
        db_updated_user = await self.uow.repository.users.update(
            telegram_id=user.telegram_id,
            **user.changed_data,
        )

        if db_updated_user:
            await self._clear_user_cache(db_updated_user.telegram_id)

        return UserDto.from_model(db_updated_user)

    async def compare_and_update(
        self,
        user: UserDto,
        aiogram_user: AiogramUser,
    ) -> Optional[UserDto]:
        new_username = aiogram_user.username
        if user.username != new_username:
            logger.debug(
                f"User '{user.telegram_id}' username changed ({user.username} -> {new_username})"
            )
            user.username = new_username

        new_name = aiogram_user.full_name
        if user.name != new_name:
            logger.debug(f"User '{user.telegram_id}' name changed ({user.name} -> {new_name})")
            user.name = new_name

        new_language = aiogram_user.language_code
        if user.language != new_language:
            if new_language in self.config.locales:
                logger.debug(
                    f"User '{user.telegram_id}' language changed "
                    f"({user.language} -> {new_language})"
                )
                user.language = Locale(new_language)
            else:
                logger.warning(
                    f"User '{user.telegram_id}' language changed. New language is not supported. "
                    f"Used default ({user.language} -> {self.config.default_locale})"
                )
                user.language = self.config.default_locale

        if not user.changed_data:
            return None

        return await self.update(user)

    async def delete(self, user: UserDto) -> bool:
        result = await self.uow.repository.users.delete(user.telegram_id)

        if result:
            await self._clear_user_cache(user.telegram_id)
            await self._remove_from_recent_registered(user.telegram_id)
            await self._remove_from_recent_activity(user.telegram_id)

        return result

    async def get_by_partial_name(self, query: str) -> list[UserDto]:
        db_users = await self.uow.repository.users.get_by_partial_name(query)
        return UserDto.from_model_list(db_users)

    @redis_cache(prefix="count", ttl=TIME_1M)
    async def count(self) -> int:
        return await self.uow.repository.users.count()

    @redis_cache(prefix="get_by_role", ttl=TIME_1M)
    async def get_by_role(self, role: UserRole) -> list[UserDto]:
        db_users = await self.uow.repository.users.filter_by_role(role)
        return UserDto.from_model_list(db_users)

    @redis_cache(prefix="get_blocked_users", ttl=TIME_10M)
    async def get_blocked_users(self) -> list[UserDto]:
        db_users = await self.uow.repository.users.filter_by_blocked(blocked=True)
        return UserDto.from_model_list(db_users)

    async def set_block(self, user: UserDto, blocked: bool) -> None:
        user.is_blocked = blocked
        await self.uow.repository.users.update(
            user.telegram_id,
            **user.changed_data,
        )
        await self._clear_user_cache(user.telegram_id)

    async def set_bot_blocked(self, user: UserDto, blocked: bool) -> None:
        user.is_bot_blocked = blocked
        await self.uow.repository.users.update(
            user.telegram_id,
            **user.changed_data,
        )
        await self._clear_user_cache(user.telegram_id)

    async def set_role(self, user: UserDto, role: UserRole) -> None:
        user.role = role
        await self.uow.repository.users.update(
            user.telegram_id,
            **user.changed_data,
        )
        await self._clear_user_cache(user.telegram_id)

    #

    async def add_to_recent_registered(self, telegram_id: int) -> None:
        await self._add_to_recent_list(RecentRegisteredUsersKey(), telegram_id)

    async def update_recent_activity(self, telegram_id: int) -> None:
        await self._add_to_recent_list(RecentActivityUsersKey(), telegram_id)

    async def get_recent_registered_users(self) -> list[UserDto]:
        telegram_ids = await self._get_recent_registered()
        db_users = await self.uow.repository.users.get_by_ids(telegram_ids)

        found_ids = {user.telegram_id for user in db_users}
        for telegram_id in telegram_ids:
            if telegram_id not in found_ids:
                logger.warning(
                    f"User '{telegram_id}' not found in DB, removing from recent registered cache"
                )
                await self._remove_from_recent_registered(telegram_id)

        logger.debug(f"Retrieved {len(db_users)} recent registered users")
        return UserDto.from_model_list(db_users)

    async def get_recent_activity_users(self) -> list[UserDto]:
        telegram_ids = await self._get_recent_activity()
        users: list[UserDto] = []

        for telegram_id in telegram_ids:
            user = await self.get(telegram_id)

            if user:
                users.append(user)
            else:
                logger.warning(
                    f"User '{telegram_id}' not found in DB, removing from recent activity cache"
                )
                await self._remove_from_recent_activity(telegram_id)

        logger.debug(f"Retrieved {len(users)} recent active users")
        return users

    async def search_users(self, message: Message) -> list[UserDto]:
        # TODO: search rs_
        found_users = []
        if message.forward_from and not message.forward_from.is_bot:
            target_telegram_id = message.forward_from.id
            single_user = await self.get(telegram_id=target_telegram_id)

            if single_user:
                found_users.append(single_user)

        elif message.text:
            search_query = message.text.strip()

            if search_query.isdigit():
                target_telegram_id = int(search_query)
                single_user = await self.get(telegram_id=target_telegram_id)

                if single_user:
                    found_users.append(single_user)
            else:
                found_users = await self.get_by_partial_name(query=search_query)

        return found_users

    #

    async def _clear_user_cache(self, telegram_id: int) -> None:
        user_cache_key: str = build_key("cache", "get_user", telegram_id)
        await self.redis_client.delete(user_cache_key)
        await self._clear_list_caches()
        logger.debug(f"User cache for '{telegram_id}' invalidated")

    async def _clear_list_caches(self) -> None:
        list_cache_keys_to_invalidate = [
            build_key("cache", "get_blocked_users"),
            build_key("cache", "count"),
        ]

        for role in UserRole:
            key = build_key("cache", "get_by_role", role=role)
            list_cache_keys_to_invalidate.append(key)

        await self.redis_client.delete(*list_cache_keys_to_invalidate)
        logger.debug("List caches invalidated")

    async def _add_to_recent_list(self, key: StorageKey, telegram_id: int) -> None:
        await self.redis_repository.list_remove(key, value=telegram_id, count=0)
        await self.redis_repository.list_push(key, telegram_id)

        if key == RecentRegisteredUsersKey():
            end = RECENT_REGISTERED_MAX_COUNT - 1
            log_message = "registered"
        else:
            end = RECENT_ACTIVITY_MAX_COUNT - 1
            log_message = "activity updated"

        await self.redis_repository.list_trim(key, start=0, end=end)
        logger.debug(f"User '{telegram_id}' {log_message} in recent cache")

    async def _remove_from_recent_registered(self, telegram_id: int) -> None:
        await self.redis_repository.list_remove(
            key=RecentRegisteredUsersKey(),
            value=telegram_id,
            count=0,
        )
        logger.debug(f"User '{telegram_id}' removed from recent registered cache")

    async def _get_recent_registered(self) -> list[int]:
        telegram_ids_str = await self.redis_repository.list_range(
            key=RecentRegisteredUsersKey(),
            start=0,
            end=RECENT_REGISTERED_MAX_COUNT - 1,
        )
        return [int(uid) for uid in telegram_ids_str]

    async def _remove_from_recent_activity(self, telegram_id: int) -> None:
        await self.redis_repository.list_remove(
            key=RecentActivityUsersKey(),
            value=telegram_id,
            count=0,
        )
        logger.debug(f"User '{telegram_id}' removed from recent activity cache")

    async def _get_recent_activity(self) -> list[int]:
        telegram_ids_str = await self.redis_repository.list_range(
            key=RecentActivityUsersKey(),
            start=0,
            end=RECENT_ACTIVITY_MAX_COUNT - 1,
        )
        return [int(uid) for uid in telegram_ids_str]
