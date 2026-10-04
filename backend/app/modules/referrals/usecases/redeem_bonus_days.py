from decimal import Decimal
from uuid import uuid4

from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.enums import Currency, PurchaseType, SubscriptionStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.referrals.dto import BonusDaysRedemptionDto, RedeemBonusDaysDto
from app.modules.referrals.events import BonusDaysRedeemedEvent
from app.modules.subscriptions import (
    PurchaseIdempotencyRepository,
    PurchaseSubscriptionDto,
    PurchaseSubscriptionUseCase,
    SubscriptionRepository,
    get_owned_target,
)
from app.modules.users import UserDto, UserRepository


class RedeemBonusDaysUseCase(UseCase[RedeemBonusDaysDto, BonusDaysRedemptionDto, UserDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        user_repository: UserRepository,
        subscription_repository: SubscriptionRepository,
        purchase_subscription_use_case: PurchaseSubscriptionUseCase,
        idempotency_repository: PurchaseIdempotencyRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._user_repository = user_repository
        self._subscription_repository = subscription_repository
        self._purchase_subscription_use_case = purchase_subscription_use_case
        self._idempotency = idempotency_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: UserDto, data: RedeemBonusDaysDto) -> BonusDaysRedemptionDto:
        async with self._uow:
            target = await get_owned_target(
                self._subscription_repository, data.subscription_id, actor.id
            )
        if target.is_trial:
            raise ValidationError(
                "Bonus days can't extend a trial", code=ErrorCode.BONUS_DAYS_TRIAL_SUBSCRIPTION
            )
        if target.status is SubscriptionStatus.DELETED:
            raise ValidationError(
                "Cannot renew a deleted subscription", code=ErrorCode.SUBSCRIPTION_DELETED
            )
        # disabled on purpose; a free extension mustn't undo that. Not re-checked
        # under the renewal's row lock, so a disable landing mid-renewal slips through
        if target.status is SubscriptionStatus.DISABLED:
            raise ValidationError(
                "Bonus days can't extend a disabled subscription",
                code=ErrorCode.BONUS_DAYS_SUBSCRIPTION_DISABLED,
            )
        if data.days > actor.bonus_days:
            raise ValidationError("Not enough bonus days", code=ErrorCode.BONUS_DAYS_INSUFFICIENT)

        # debit first: the balance's DB floor is what stops a concurrent double spend
        try:
            async with self._uow:
                await self._user_repository.credit_bonus_days(actor.id, -data.days)
        except ValidationError as error:
            # a concurrent redemption spent the balance after the check above
            raise ValidationError(
                "Not enough bonus days", code=ErrorCode.BONUS_DAYS_INSUFFICIENT
            ) from error
        key = str(uuid4())
        renewal = PurchaseSubscriptionDto(
            user_id=actor.id,
            plan_snapshot=target.plan_snapshot,
            duration_days=data.days,
            price_paid=Decimal(0),
            currency=Currency.USD,
            purchase_type=PurchaseType.RENEW,
            target_subscription_id=target.id,
            idempotency_key=key,
        )
        try:
            subscription = await self._purchase_subscription_use_case(actor, renewal)
        except Exception:
            async with self._uow:
                pinned = await self._idempotency.get_pending_renew_expire_at(key)
            if pinned is None:
                # the panel was never written: give the days back
                # (a crash before this refund loses them)
                async with self._uow:
                    await self._user_repository.credit_bonus_days(actor.id, data.days)
                raise
            # the panel may already hold the new date; a refund would hand out
            # the days twice, so resume the same renewal instead
            logger.warning(
                f"{actor.log} Bonus days renewal '{key}' failed after pinning its date, retrying"
            )
            subscription = await self._purchase_subscription_use_case(actor, renewal)

        async with self._uow:
            await self._event_publisher.publish(
                BonusDaysRedeemedEvent(user=actor, subscription_id=subscription.id, days=data.days)
            )
            refreshed = await self._user_repository.get_by_id(actor.id)
            if refreshed is None:
                raise NotFoundError(f"User '{actor.id}' not found", code=ErrorCode.USER_NOT_FOUND)

        logger.info(
            f"{actor.log} Redeemed '{data.days}' bonus days on subscription '{subscription.id}'"
        )
        return BonusDaysRedemptionDto(
            subscription_id=subscription.id,
            expire_at=subscription.expire_at,
            bonus_days=refreshed.bonus_days,
        )
