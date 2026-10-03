from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.modules.blacklist import BlacklistRepository
from app.modules.users.display_name import clean_telegram_name
from app.modules.users.dto import CreateUserDto, RegisterTelegramUserDto, UserDto
from app.modules.users.events import TelegramRegistrationBlockedEvent, TelegramUserRegisteredEvent
from app.modules.users.repository import UserRepository


class RegisterTelegramUserUseCase(UseCase[RegisterTelegramUserDto, UserDto]):
    # no actor exists yet on a user's first contact; required_permission=None
    # makes it callable only via `.system`
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
            # lost a race with another update from the same new telegram_id;
            # the winner's row exists, so use it
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
