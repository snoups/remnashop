from dataclasses import dataclass
from typing import Optional

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.modules.blacklist import BlacklistRepository
from app.modules.users.display_name import clean_telegram_name
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.events import TelegramRegistrationBlockedEvent, TelegramUserRegisteredEvent
from app.modules.users.repository import UserRepository


@dataclass(frozen=True, kw_only=True)
class RegisterTelegramUserDto:
    telegram_id: int
    name: str
    username: Optional[str] = None
    language: Locale
    # True when `language` is the user's own Telegram language (and active),
    # not the deployment default -- only then may it overwrite a stored one.
    sync_language: bool = False
    # Raw deep-link payloads, opaque to `users` -- advertising and referrals
    # resolve them.
    ad_link_code: Optional[str] = None
    referral_code: Optional[str] = None


class RegisterTelegramUserUseCase(UseCase[RegisterTelegramUserDto, UserDto]):
    # No permission gate: there is structurally no actor yet on a user's first
    # Telegram contact. Only callable via `.system` -- _check_permissions()
    # denies any other actor outright since required_permission is None.
    required_permission = None

    def __init__(
        self,
        user_repository: UserRepository,
        blacklist_repository: BlacklistRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._user_repository = user_repository
        self._blacklist_repository = blacklist_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: RegisterTelegramUserDto) -> UserDto:
        async with self._uow:
            existing = await self._user_repository.get_by_telegram_id(data.telegram_id)
            if existing is not None:
                return await self._sync_profile(existing, data)

            is_blocked = await self._blacklist_repository.is_blacklisted_telegram_id(
                data.telegram_id
            )

        try:
            async with self._uow:
                user = await self._user_repository.create(
                    CreateUserDto(
                        telegram_id=data.telegram_id,
                        name=clean_telegram_name(data.name, data.telegram_id),
                        username=data.username,
                        language=data.language,
                        is_blocked=is_blocked,
                    )
                )
                if is_blocked:
                    await self._event_publisher.publish(TelegramRegistrationBlockedEvent(user=user))
                    return user
                await self._event_publisher.publish(
                    TelegramUserRegisteredEvent(
                        user=user,
                        ad_link_code=data.ad_link_code,
                        referral_code=data.referral_code,
                    )
                )
        except ConflictError as error:
            if error.code is not ErrorCode.TELEGRAM_ID_TAKEN:
                raise
            # Lost a concurrent registration race (two updates from the same
            # brand-new telegram_id in flight at once) -- the winner's row
            # already exists, fetch it instead of dropping this update.
            logger.debug(f"Lost registration race for telegram_id={data.telegram_id}")
            async with self._uow:
                winner = await self._user_repository.get_by_telegram_id(data.telegram_id)
            if winner is None:
                raise
            return winner

        return user

    async def _sync_profile(self, user: UserDto, data: RegisterTelegramUserDto) -> UserDto:
        # staff names are set from the dashboard, Telegram doesn't own them
        name = (
            clean_telegram_name(data.name, data.telegram_id)
            if user.role == Role.USER
            else user.name
        )
        language = data.language if data.sync_language else user.language
        if (user.name, user.username, user.language) == (name, data.username, language):
            return user
        updated = await self._user_repository.update_telegram_profile(
            user.id, name=name, username=data.username, language=language
        )
        logger.info(f"User '{user.id}' profile updated from Telegram data")
        return updated
