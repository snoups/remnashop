from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.referrals.dto import AdjustUserBonusDaysDto
from app.modules.referrals.events import UserBonusDaysAdjustedEvent
from app.modules.users import UserRepository


class AdjustUserBonusDaysUseCase(UseCase[AdjustUserBonusDaysDto, None]):
    required_permission = Permission.REFERRALS_BONUS_DAYS_MANAGE

    def __init__(
        self, user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
    ) -> None:
        self._user_repository = user_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: AdjustUserBonusDaysDto) -> None:
        async with self._uow:
            target = await self._user_repository.get_by_id(data.user_id)
            if target is None:
                raise NotFoundError(
                    f"User '{data.user_id}' not found", code=ErrorCode.USER_NOT_FOUND
                )
            # the floor itself is in credit_bonus_days' UPDATE predicate
            await self._user_repository.credit_bonus_days(data.user_id, data.delta)
            await self._event_publisher.publish(
                UserBonusDaysAdjustedEvent(actor=actor, target=target, delta=data.delta)
            )
        logger.info(f"{actor.log} Adjusted bonus days of user '{data.user_id}' by '{data.delta}'")
