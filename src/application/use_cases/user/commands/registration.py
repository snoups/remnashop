from dataclasses import dataclass
from typing import Optional, Self

from aiogram.types import ChatMemberUpdated, TelegramObject
from aiogram.types import User as AiogramUser
from loguru import logger

from src.application.common import Cryptographer, EventPublisher, Interactor
from src.application.common.dao import UserDao
from src.application.common.uow import UnitOfWork
from src.application.dto import UserDto
from src.application.events import UserRegisteredEvent
from src.application.use_cases.referral.commands.attachment import AttachReferral, AttachReferralDto
from src.application.use_cases.referral.queries.code import GetReferralCodeFromEvent
from src.core.config import AppConfig
from src.core.enums import Locale, Role
from src.core.utils.converters import user_name_clean


@dataclass
class GetOrCreateUserDto:
    telegram_id: int
    username: Optional[str]
    full_name: str
    language_code: Optional[str]
    event: TelegramObject
    role: Role = Role.USER

    @classmethod
    def from_aiogram(cls, user: AiogramUser, event: TelegramObject) -> Self:
        return cls(
            telegram_id=user.id,
            username=user.username,
            full_name=user.full_name,
            language_code=user.language_code,
            event=event,
        )


class GetOrCreateUser(Interactor[GetOrCreateUserDto, Optional[UserDto]]):
    required_permission = None

    def __init__(
        self,
        uow: UnitOfWork,
        user_dao: UserDao,
        config: AppConfig,
        cryptographer: Cryptographer,
        event_publisher: EventPublisher,
        get_referral_code_from_event: GetReferralCodeFromEvent,
        attach_referral: AttachReferral,
    ) -> None:
        self.uow = uow
        self.user_dao = user_dao
        self.config = config
        self.cryptographer = cryptographer
        self.event_publisher = event_publisher
        self.get_referral_code_from_event = get_referral_code_from_event
        self.attach_referral = attach_referral

    async def _execute(self, actor: UserDto, data: GetOrCreateUserDto) -> Optional[UserDto]:
        async with self.uow:
            user = await self.user_dao.get_by_telegram_id(data.telegram_id)
            if user:
                return user

            if data.event.__class__.__name__ == ChatMemberUpdated.__name__:
                logger.debug(
                    f"Skipping user creation for '{data.telegram_id}' "
                    f"due to '{ChatMemberUpdated.__name__}' event"
                )
                return None

            is_owner = data.telegram_id == self.config.bot.owner_id

            if is_owner:
                data.role = Role.OWNER
                old_owner = await self.user_dao.filter_by_role([Role.OWNER])
                if old_owner:
                    old_owner[0].role = Role.DEV
                    await self.user_dao.update(old_owner[0])

            user_dto = self._create_user_dto(data)
            user = await self.user_dao.create(user_dto)
            await self.uow.commit()

        referrer = None
        referral_code = await self.get_referral_code_from_event.system(data.event)
        if referral_code:
            referrer = await self.attach_referral.system(
                AttachReferralDto(user.telegram_id, referral_code)
            )

        await self.event_publisher.publish(
            UserRegisteredEvent(
                telegram_id=user.telegram_id,
                username=user.username,
                name=user.name,
                referrer_telegram_id=referrer.telegram_id if referrer else None,
                referrer_username=referrer.username if referrer else None,
                referrer_name=referrer.name if referrer else None,
            )
        )

        logger.info(f"New user '{user.telegram_id}' created")
        return user

    def _create_user_dto(self, data: GetOrCreateUserDto) -> UserDto:
        if data.language_code in self.config.locales:
            locale = Locale(data.language_code)
        else:
            locale = self.config.default_locale

        return UserDto(
            telegram_id=data.telegram_id,
            username=data.username,
            referral_code=self.cryptographer.generate_short_code(data.telegram_id),
            name=data.full_name,
            role=data.role,
            language=locale,
        )


@dataclass(frozen=True)
class UpdateUserFromTelegramDto:
    user: UserDto
    aiogram_user: AiogramUser


class UpdateUserFromTelegram(Interactor[UpdateUserFromTelegramDto, UserDto]):
    required_permission = None

    def __init__(self, uow: UnitOfWork, user_dao: UserDao, config: AppConfig) -> None:
        self.uow = uow
        self.user_dao = user_dao
        self.config = config

    async def _execute(self, actor: UserDto, data: UpdateUserFromTelegramDto) -> UserDto:
        user = data.user
        aiogram_user = data.aiogram_user
        changed = False

        new_username = aiogram_user.username
        if user.username != new_username:
            logger.debug(
                f"User '{user.telegram_id}' username changed from "
                f"'{user.username}' to '{new_username}'"
            )
            user.username = new_username
            changed = True

        new_name = user_name_clean(aiogram_user.full_name, aiogram_user.id)
        if user.name != new_name:
            logger.debug(
                f"User '{user.telegram_id}' name changed from '{user.name}' to '{new_name}'"
            )
            user.name = new_name
            changed = True

        new_language = aiogram_user.language_code
        if new_language and user.language != new_language:
            if new_language in self.config.locales:
                logger.debug(
                    f"User '{user.telegram_id}' language changed from "
                    f"'{user.language}' to '{new_language}'"
                )
                user.language = Locale(new_language)
                changed = True
            else:
                logger.warning(
                    f"User '{user.telegram_id}' language '{new_language}' is not supported, "
                    f"keeping current '{user.language}'"
                )

        if not changed:
            return user

        async with self.uow:
            updated_user = await self.user_dao.update(user)
            if updated_user:
                logger.info(f"User '{user.telegram_id}' profile updated from Telegram data")
            await self.uow.commit()

        return updated_user or user
