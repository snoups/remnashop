from dataclasses import dataclass
from decimal import Decimal

from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.referrals.events import PointsWithdrawalRequestedEvent
from app.modules.users import UserDto


@dataclass(frozen=True, kw_only=True)
class RequestPointsWithdrawalDto:
    amount: Decimal


class RequestPointsWithdrawalUseCase(UseCase[RequestPointsWithdrawalDto, None, UserDto]):
    required_permission = Permission.PUBLIC

    def __init__(self, uow: UnitOfWork, event_publisher: EventPublisher) -> None:
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: UserDto, data: RequestPointsWithdrawalDto) -> None:
        if data.amount <= 0:
            raise ValidationError(
                "Withdrawal amount must be positive", code=ErrorCode.WITHDRAWAL_AMOUNT_INVALID
            )
        if data.amount > actor.points:
            raise ValidationError(
                "Withdrawal amount exceeds current points", code=ErrorCode.WITHDRAWAL_EXCEEDS_POINTS
            )

        async with self._uow:
            await self._event_publisher.publish(
                PointsWithdrawalRequestedEvent(user=actor, amount=str(data.amount))
            )
        logger.info(f"{actor.log} Requested points withdrawal of '{data.amount}'")
