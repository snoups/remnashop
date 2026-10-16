from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.events import UserEvent
from app.core.exceptions import ConflictError
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.core.utils.email import normalize_email
from app.modules.blacklist import BlacklistRepository
from app.modules.users.dto import CreateUserDto, RegisterCabinetUserDto, UserDto
from app.modules.users.events import (
    CabinetRegistrationBlockedEvent,
    CabinetUserRegisteredEvent,
)
from app.modules.users.repository import UserRepository


class RegisterCabinetUserUseCase(UseCase[RegisterCabinetUserDto, UserDto]):
    # first contact, no actor yet; callable only via `.system`
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

    async def _execute(self, actor: Actor, data: RegisterCabinetUserDto) -> UserDto:
        email = normalize_email(data.email) if data.email else None
        is_blocked = False
        if email is not None:
            async with self._uow:
                is_blocked = await self._blacklist_repository.is_blacklisted_email(email)

        try:
            async with self._uow:
                user = await self._user_repository.create(
                    CreateUserDto(
                        name=data.name, language=data.language, email=email, is_blocked=is_blocked
                    )
                )
                if data.snapshot is not None:
                    await self._user_repository.add_registration(user.id, data.snapshot)
                event: UserEvent = (
                    CabinetRegistrationBlockedEvent(user=user)
                    if is_blocked
                    else CabinetUserRegisteredEvent(
                        user=user,
                        method=data.method.value,
                        ad_link_code=data.ad_link_code,
                        referral_code=data.referral_code,
                    )
                )
                await self._event_publisher.publish(event)
        except ConflictError as error:
            if error.code is not ErrorCode.EMAIL_TAKEN or email is None:
                raise
            # lost a race for the same email; the winner's row exists
            logger.debug("Lost a cabinet registration race for an email")
            async with self._uow:
                winner = await self._user_repository.get_by_email(email)
            if winner is None:
                raise
            return winner

        return user
