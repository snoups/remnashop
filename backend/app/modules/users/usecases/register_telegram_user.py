from dataclasses import dataclass
from typing import Optional

from loguru import logger
from sqlalchemy.exc import IntegrityError

from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.modules.blacklist import BlacklistRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.events import TelegramRegistrationBlockedEvent, TelegramUserRegisteredEvent
from app.modules.users.repository import UserRepository


@dataclass(frozen=True, kw_only=True)
class RegisterTelegramUserDto:
    telegram_id: int
    name: str
    language: Locale
    # Raw deep-link payload, opaque to `users` -- advertising resolves it.
    ad_link_code: Optional[str] = None


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

    async def _execute(self, actor: UserDto, data: RegisterTelegramUserDto) -> UserDto:
        async with self._uow:
            existing = await self._user_repository.get_by_telegram_id(data.telegram_id)
            if existing is not None:
                return existing

            is_blocked = await self._blacklist_repository.is_blacklisted_telegram_id(
                data.telegram_id
            )

        try:
            async with self._uow:
                user = await self._user_repository.create(
                    CreateUserDto(
                        telegram_id=data.telegram_id,
                        name=data.name,
                        language=data.language,
                        is_blocked=is_blocked,
                    )
                )
                if is_blocked:
                    await self._event_publisher.publish(TelegramRegistrationBlockedEvent(user=user))
                    return user
                await self._event_publisher.publish(
                    TelegramUserRegisteredEvent(user=user, ad_link_code=data.ad_link_code)
                )
        except IntegrityError:
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
