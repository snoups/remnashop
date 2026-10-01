from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.referrals.events import ReferralCodeResetEvent
from app.modules.users import UserDto, UserRepository


class ResetReferralCodeUseCase(UseCase[int, UserDto]):
    required_permission = Permission.REFERRALS_CODE_RESET

    def __init__(
        self, user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
    ) -> None:
        self._user_repository = user_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: int) -> UserDto:
        async with self._uow:
            updated = await self._user_repository.reset_referral_code(data)
            if updated is None:
                raise NotFoundError(f"User '{data}' not found", code=ErrorCode.USER_NOT_FOUND)
            await self._event_publisher.publish(ReferralCodeResetEvent(actor=actor, target=updated))

        logger.info(f"{actor.log} Reset referral code of user '{data}'")
        return updated
