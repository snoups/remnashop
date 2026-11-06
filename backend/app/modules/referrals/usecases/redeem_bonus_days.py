from dataclasses import replace
from functools import partial
from typing import Optional
from uuid import uuid4

from loguru import logger

from app.core.constants import ZERO_AMOUNT
from app.core.db.uow import UnitOfWork
from app.core.enums import Currency, PurchaseType
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.referrals.bonus_targets import BonusDaysTargets
from app.modules.referrals.dispatch import BonusRenewalDispatch
from app.modules.referrals.dto import MAX_BONUS_DAYS, BonusDaysRedemptionDto, RedeemBonusDaysDto
from app.modules.referrals.events import BonusDaysRedeemedEvent, BonusDaysRenewalStuckEvent
from app.modules.referrals.failures import is_infrastructure_error
from app.modules.subscriptions import (
    PurchaseIdempotencyRepository,
    PurchaseSubscriptionDto,
    PurchaseSubscriptionUseCase,
    SubscriptionDto,
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
        targets: BonusDaysTargets,
        purchase_subscription_use_case: PurchaseSubscriptionUseCase,
        idempotency_repository: PurchaseIdempotencyRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
        bonus_renewal_dispatch: BonusRenewalDispatch,
    ) -> None:
        self._user_repository = user_repository
        self._subscription_repository = subscription_repository
        self._targets = targets
        self._purchase_subscription_use_case = purchase_subscription_use_case
        self._idempotency = idempotency_repository
        self._uow = uow
        self._event_publisher = event_publisher
        self._bonus_renewal_dispatch = bonus_renewal_dispatch

    async def _execute(self, actor: UserDto, data: RedeemBonusDaysDto) -> BonusDaysRedemptionDto:
        async with self._uow:
            target = await get_owned_target(
                self._subscription_repository, data.subscription_id, actor.id
            )
        await self._targets.assert_accepts(target)
        if data.days > MAX_BONUS_DAYS:
            raise ValidationError(
                f"At most {MAX_BONUS_DAYS} bonus days at once",
                code=ErrorCode.BONUS_DAYS_ABOVE_LIMIT,
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
            price_paid=ZERO_AMOUNT,
            currency=Currency.USD,
            purchase_type=PurchaseType.RENEW,
            target_subscription_id=target.id,
            idempotency_key=key,
        )
        try:
            subscription = await self._purchase_subscription_use_case(actor, renewal)
        except Exception:
            async with self._uow:
                pinned = await self._idempotency.find_pending_renew_expire_at(key)
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
            try:
                # the pinned date is owed now: a disable since must not strand the days
                subscription = await self._purchase_subscription_use_case(
                    actor, replace(renewal, refuse_disabled_target=False)
                )
            except Exception as error:
                if not is_infrastructure_error(error):
                    # retrying won't help, and the date may be on the panel, so no refund either
                    async with self._uow:
                        await self._event_publisher.publish(
                            BonusDaysRenewalStuckEvent(
                                user_id=actor.id,
                                subscription_id=target.id,
                                days=data.days,
                                idempotency_key=key,
                                error=str(error)[:255],
                            )
                        )
                    raise
                logger.exception(
                    f"{actor.log} Bonus days renewal '{key}' failed again, handing it to the worker"
                )
                return await self._finish(actor, data, target, pending_key=key)
        return await self._finish(actor, data, subscription)

    async def _finish(
        self,
        actor: UserDto,
        data: RedeemBonusDaysDto,
        subscription: SubscriptionDto,
        *,
        pending_key: Optional[str] = None,
    ) -> BonusDaysRedemptionDto:
        async with self._uow:
            if pending_key is not None:
                # the days stay debited; the worker completes the same pinned key
                await self._uow.after_commit(
                    partial(
                        self._bonus_renewal_dispatch.kiq,
                        user_id=actor.id,
                        subscription_id=subscription.id,
                        days=data.days,
                        idempotency_key=pending_key,
                    )
                )
            await self._event_publisher.publish(
                BonusDaysRedeemedEvent(user=actor, subscription_id=subscription.id, days=data.days)
            )
            refreshed = await self._user_repository.find_by_id(actor.id)
            if refreshed is None:
                raise NotFoundError(f"User '{actor.id}' not found", code=ErrorCode.USER_NOT_FOUND)

        logger.info(
            f"{actor.log} Redeemed '{data.days}' bonus days on subscription '{subscription.id}'"
        )
        return BonusDaysRedemptionDto(
            subscription_id=subscription.id,
            expire_at=subscription.expire_at,
            bonus_days=refreshed.bonus_days,
            pending=pending_key is not None,
        )
