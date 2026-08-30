from decimal import Decimal
from typing import Final, Optional

from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.enums import (
    Currency,
    PromocodeAvailability,
    PromocodeRewardType,
    PurchaseType,
    SubscriptionStatus,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.promocodes.dto import ActivatePromocodeDto, PromocodeDto
from app.modules.promocodes.events import PromocodeActivatedEvent
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.subscriptions import (
    MAX_ACTIVE_SUBSCRIPTIONS_PER_USER,
    GrantAddOnDto,
    GrantAddOnUseCase,
    PurchaseSubscriptionDto,
    PurchaseSubscriptionUseCase,
    SubscriptionDto,
    SubscriptionRepository,
)
from app.modules.users import UserDto

_TARGET_REQUIRED_REWARDS: Final[frozenset[PromocodeRewardType]] = frozenset(
    {PromocodeRewardType.DURATION, PromocodeRewardType.TRAFFIC, PromocodeRewardType.DEVICES}
)


class ActivatePromocodeUseCase(UseCase[ActivatePromocodeDto, PromocodeDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        promocode_repository: PromocodeRepository,
        subscription_repository: SubscriptionRepository,
        purchase_subscription_use_case: PurchaseSubscriptionUseCase,
        grant_addon_use_case: GrantAddOnUseCase,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._promocode_repository = promocode_repository
        self._subscription_repository = subscription_repository
        self._purchase_subscription_use_case = purchase_subscription_use_case
        self._grant_addon_use_case = grant_addon_use_case
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: UserDto, data: ActivatePromocodeDto) -> PromocodeDto:
        code = data.code.strip().upper()
        promo = await self._promocode_repository.get_by_code(code)
        if promo is None or not promo.is_active:
            raise NotFoundError(f"Promocode '{code}' not found")

        if promo.expires_at is not None and datetime_now() > promo.expires_at:
            raise ValidationError(f"Promocode '{code}' has expired")

        await self._check_availability(actor, promo)

        target: Optional[SubscriptionDto] = None
        if promo.reward_type in _TARGET_REQUIRED_REWARDS:
            if data.target_subscription_id is None:
                raise ValidationError("target_subscription_id is required for this promocode")
            try:
                target = await self._subscription_repository.get_by_id(data.target_subscription_id)
            except NotFoundError as error:
                raise ValidationError(
                    "target_subscription_id does not belong to this user"
                ) from error
            if target.user_id != actor.id:
                raise ValidationError("target_subscription_id does not belong to this user")
            if target.status is not SubscriptionStatus.ACTIVE:
                raise ValidationError("target_subscription_id must be an active subscription")
        elif promo.reward_type is PromocodeRewardType.SUBSCRIPTION:
            active = await self._subscription_repository.get_active_by_user(actor.id)
            if len(active) >= MAX_ACTIVE_SUBSCRIPTIONS_PER_USER:
                raise ValidationError(
                    f"User '{actor.id}' is already at the concurrent-subscription cap"
                )

        async with self._uow:
            await self._promocode_repository.claim_activation(
                promocode_id=promo.id,
                user_id=actor.id,
                subscription_id=target.id if target is not None else None,
            )

        await self._apply_reward(actor, promo, target)

        logger.info(f"{actor.log} Activated promocode '{promo.code}'")
        await self._event_publisher.publish(
            PromocodeActivatedEvent(
                user=actor, promocode_id=promo.id, reward_type=promo.reward_type.value
            )
        )
        return promo

    async def _check_availability(self, actor: UserDto, promo: PromocodeDto) -> None:
        if promo.availability is PromocodeAvailability.ALL:
            return
        if promo.availability is PromocodeAvailability.NEW:
            active = await self._subscription_repository.get_active_by_user(actor.id)
            if active:
                raise ValidationError(f"Promocode '{promo.code}' is for new users only")
            return
        if promo.availability is PromocodeAvailability.EXISTING:
            active = await self._subscription_repository.get_active_by_user(actor.id)
            if not active:
                raise ValidationError(f"Promocode '{promo.code}' is for existing users only")
            return
        if promo.availability is PromocodeAvailability.ALLOWED:
            if actor.id not in promo.allowed_user_ids:
                raise ValidationError(f"Promocode '{promo.code}' is not available to this user")
            return
        # INVITED: no modules.referrals exists yet to check against -- always deny,
        # same pattern ListActivePlansUseCase already uses for the same gap.
        raise ValidationError(f"Promocode '{promo.code}' is not available to this user")

    async def _apply_reward(
        self, actor: UserDto, promo: PromocodeDto, target: Optional[SubscriptionDto]
    ) -> None:
        try:
            if promo.reward_type is PromocodeRewardType.DURATION:
                assert target is not None
                assert promo.reward is not None
                await self._purchase_subscription_use_case(
                    actor,
                    PurchaseSubscriptionDto(
                        user_id=actor.id,
                        plan_id=target.plan_snapshot.plan_id,
                        duration_days=promo.reward,
                        price_paid=Decimal(0),
                        currency=Currency.USD,
                        purchase_type=PurchaseType.RENEW,
                        target_subscription_id=target.id,
                    ),
                )
            elif promo.reward_type in (PromocodeRewardType.TRAFFIC, PromocodeRewardType.DEVICES):
                assert target is not None
                assert promo.reward_addon_id is not None
                await self._grant_addon_use_case.system(
                    GrantAddOnDto(subscription_id=target.id, addon_id=promo.reward_addon_id)
                )
            elif promo.reward_type is PromocodeRewardType.SUBSCRIPTION:
                assert promo.reward_plan_id is not None
                assert promo.reward_duration_days is not None
                await self._purchase_subscription_use_case(
                    actor,
                    PurchaseSubscriptionDto(
                        user_id=actor.id,
                        plan_id=promo.reward_plan_id,
                        duration_days=promo.reward_duration_days,
                        price_paid=Decimal(0),
                        currency=Currency.USD,
                        purchase_type=PurchaseType.NEW,
                    ),
                )
        except Exception:
            # The claim above is already committed -- an orphaned activation
            # with no reward, not a double-grant past a limit. Same accepted
            # dual-write risk shape as GrantAddOnUseCase's own sibling code.
            logger.error(
                f"{actor.log} Promocode '{promo.code}' activation recorded but reward "
                f"application failed -- possible orphaned activation"
            )
            raise
