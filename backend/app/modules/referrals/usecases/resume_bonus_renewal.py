from decimal import Decimal

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import Currency, PurchaseType
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.usecase import UseCase
from app.modules.referrals.dto import ResumeBonusRenewalDto
from app.modules.subscriptions import (
    PurchaseSubscriptionDto,
    PurchaseSubscriptionUseCase,
    SubscriptionRepository,
)
from app.modules.users import UserRepository


class ResumeBonusRenewalUseCase(UseCase[ResumeBonusRenewalDto, None]):
    """Finishes a bonus-days renewal whose date is pinned; the shared key makes
    a repeat a no-op, so the days can't land twice."""

    required_permission = None

    def __init__(
        self,
        user_repository: UserRepository,
        subscription_repository: SubscriptionRepository,
        purchase_subscription_use_case: PurchaseSubscriptionUseCase,
        uow: UnitOfWork,
    ) -> None:
        self._user_repository = user_repository
        self._subscription_repository = subscription_repository
        self._purchase_subscription_use_case = purchase_subscription_use_case
        self._uow = uow

    async def _execute(self, actor: Actor, data: ResumeBonusRenewalDto) -> None:
        async with self._uow:
            user = await self._user_repository.get_by_id(data.user_id)
            if user is None:
                raise NotFoundError(
                    f"User '{data.user_id}' not found", code=ErrorCode.USER_NOT_FOUND
                )
            target = await self._subscription_repository.get_by_id(data.subscription_id)
        # the pinned date is owed: a disable since must not strand the days
        subscription = await self._purchase_subscription_use_case(
            user,
            PurchaseSubscriptionDto(
                user_id=user.id,
                plan_snapshot=target.plan_snapshot,
                duration_days=data.days,
                price_paid=Decimal(0),
                currency=Currency.USD,
                purchase_type=PurchaseType.RENEW,
                target_subscription_id=target.id,
                idempotency_key=data.idempotency_key,
                refuse_disabled_target=False,
            ),
        )
        logger.info(
            f"{user.log} Resumed bonus days renewal '{data.idempotency_key}' "
            f"on subscription '{subscription.id}'"
        )
