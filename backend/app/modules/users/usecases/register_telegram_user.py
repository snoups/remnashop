from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import AdLinkChannel, CabinetSignInMethod
from app.core.error_codes import ErrorCode
from app.core.events import UserEvent
from app.core.exceptions import ConflictError
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.modules.blacklist import BlacklistRepository
from app.modules.users.display_name import clean_display_name
from app.modules.users.dto import CreateUserDto, RegisterTelegramUserDto, UserDto
from app.modules.users.events import (
    CabinetUserRegisteredEvent,
    TelegramRegistrationBlockedEvent,
    TelegramUserRegisteredEvent,
)
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
            existing = await self._user_repository.find_by_telegram_id(data.telegram_id)
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
                        name=clean_display_name(data.name),
                        username=data.username,
                        language=data.language,
                        is_blocked=is_blocked,
                    )
                )
                if data.snapshot is not None:
                    await self._user_repository.add_registration(user.id, data.snapshot)
                if is_blocked:
                    await self._event_publisher.publish(TelegramRegistrationBlockedEvent(user=user))
                    return user
                event: UserEvent = (
                    CabinetUserRegisteredEvent(
                        user=user,
                        method=CabinetSignInMethod.TELEGRAM,
                        ad_link_code=data.ad_link_code,
                        referral_code=data.referral_code,
                    )
                    if data.channel is AdLinkChannel.WEBCABINET
                    else TelegramUserRegisteredEvent(
                        user=user,
                        ad_link_code=data.ad_link_code,
                        referral_code=data.referral_code,
                    )
                )
                await self._event_publisher.publish(event)
        except ConflictError as error:
            if error.code is not ErrorCode.TELEGRAM_ID_TAKEN:
                raise
            # lost a race with another update from the same new telegram_id;
            # the winner's row exists, so use it
            logger.debug(f"Lost registration race for telegram_id={data.telegram_id}")
            async with self._uow:
                winner = await self._user_repository.find_by_telegram_id(data.telegram_id)
            if winner is None:
                raise
            return winner

        return user

    async def _sync_profile(self, user: UserDto, data: RegisterTelegramUserDto) -> UserDto:
        # staff names are set from the dashboard, Telegram doesn't own them
        name = clean_display_name(data.name) if user.is_customer else user.name
        # staff language comes from the dashboard and drives their notifications
        sync_language = data.sync_language and user.is_customer
        language = data.language if sync_language else user.language
        if user.is_bot_blocked and await self._user_repository.set_bot_blocked(user.id, False):
            user = user.model_copy(update={"is_bot_blocked": False})
        if (user.name, user.username, user.language) == (name, data.username, language):
            return user
        updated = await self._user_repository.update_telegram_profile(
            user.id, name=name, username=data.username, language=language
        )
        logger.info(f"{user.log} Updated profile from Telegram data")
        return updated
