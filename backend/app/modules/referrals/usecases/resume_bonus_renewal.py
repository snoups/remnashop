from loguru import logger

from app.core.actor import Actor
from app.core.constants import ZERO_AMOUNT
from app.core.db.uow import UnitOfWork
from app.core.enums import Currency, PurchaseType
from app.core.error_codes import ErrorCode
from app.core.exceptions import (
    NotFoundError,
    RetryableTaskError,
)
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.modules.referrals.dto import ResumeBonusRenewalDto
from app.modules.referrals.events import BonusDaysRenewalStuckEvent
from app.modules.referrals.failures import is_infrastructure_error
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
        event_publisher: EventPublisher,
    ) -> None:
        self._user_repository = user_repository
        self._subscription_repository = subscription_repository
        self._purchase_subscription_use_case = purchase_subscription_use_case
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: ResumeBonusRenewalDto) -> None:
        # the pinned date is owed: a disable since must not strand the days
        try:
            async with self._uow:
                user = await self._user_repository.find_by_id(data.user_id)
                if user is None:
                    raise NotFoundError(
                        f"User '{data.user_id}' not found", code=ErrorCode.USER_NOT_FOUND
                    )
                target = await self._subscription_repository.get_by_id(data.subscription_id)
            subscription = await self._purchase_subscription_use_case(
                user,
                PurchaseSubscriptionDto(
                    user_id=user.id,
                    plan_snapshot=target.plan_snapshot,
                    duration_days=data.days,
                    price_paid=ZERO_AMOUNT,
                    currency=Currency.USD,
                    purchase_type=PurchaseType.RENEW,
                    target_subscription_id=target.id,
                    idempotency_key=data.idempotency_key,
                    refuse_disabled_target=False,
                ),
            )
        except Exception as error:
            if is_infrastructure_error(error) and not data.final_attempt:
                # the date is pinned under the same key, so a repeat can't extend twice
                raise RetryableTaskError(str(error)) from error
            logger.exception(f"Bonus days renewal '{data.idempotency_key}' is stuck")
            async with self._uow:
                await self._event_publisher.publish(
                    BonusDaysRenewalStuckEvent(
                        user_id=data.user_id,
                        subscription_id=data.subscription_id,
                        days=data.days,
                        idempotency_key=data.idempotency_key,
                        error=str(error)[:255],
                    )
                )
            return
        logger.info(
            f"{user.log} Resumed bonus days renewal '{data.idempotency_key}' "
            f"on subscription '{subscription.id}'"
        )
