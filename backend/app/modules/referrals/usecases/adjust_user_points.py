from loguru import logger

from app.core.actor import Actor
from app.core.constants import MAX_POINTS_BALANCE
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.referrals.dto import AdjustUserPointsDto
from app.modules.referrals.events import UserPointsAdjustedEvent
from app.modules.users import UserDto, UserRepository, assert_own_or_manageable, get_visible_target


class AdjustUserPointsUseCase(UseCase[AdjustUserPointsDto, UserDto]):
    required_permission = Permission.REFERRALS_POINTS_MANAGE

    def __init__(
        self, user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
    ) -> None:
        self._user_repository = user_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: AdjustUserPointsDto) -> UserDto:
        async with self._uow:
            target = await get_visible_target(
                self._user_repository, actor, data.user_id, for_update=True
            )
            assert_own_or_manageable(actor, target)

            # Belt-and-braces: the authoritative floor lives in credit_points' own
            # UPDATE predicate (two concurrent debits would both pass a check made
            # here); this only gives the common case its own error code.
            if target.points + data.delta < 0:
                raise ValidationError(
                    f"Adjustment would take user '{data.user_id}' points below zero",
                    code=ErrorCode.POINTS_BELOW_ZERO,
                )
            if target.points + data.delta > MAX_POINTS_BALANCE:
                raise ValidationError(
                    f"Adjustment would take user '{data.user_id}' points above the limit",
                    code=ErrorCode.POINTS_LIMIT_EXCEEDED,
                )

            await self._user_repository.credit_points(data.user_id, data.delta)
            await self._event_publisher.publish(
                UserPointsAdjustedEvent(
                    actor=actor, target=target, delta=str(data.delta), ip_address=data.client_ip
                )
            )

            updated = await self._user_repository.find_by_id(data.user_id)
            if updated is None:
                raise NotFoundError(
                    f"User '{data.user_id}' not found", code=ErrorCode.USER_NOT_FOUND
                )

            logger.info(f"{actor.log} Adjusted points of user '{data.user_id}' by '{data.delta}'")
            return updated
