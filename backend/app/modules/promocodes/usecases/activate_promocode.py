from decimal import Decimal
from typing import Final, Optional

from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.enums import (
    Currency,
    PromocodeRewardType,
    PurchaseType,
    SubscriptionStatus,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.plans import PlanRepository, is_plan_purchasable_by
from app.modules.promocodes.availability import assert_available_to
from app.modules.promocodes.dto import ActivatePromocodeDto, PromocodeDto
from app.modules.promocodes.events import PromocodeActivatedEvent
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.referrals import ReferralRepository
from app.modules.settings import SettingsRepository
from app.modules.subscriptions import (
    GrantAddOnDto,
    GrantAddOnUseCase,
    PlanSnapshot,
    PurchaseSubscriptionDto,
    PurchaseSubscriptionUseCase,
    SubscriptionDto,
    SubscriptionRepository,
)
from app.modules.users import UpdateUserDto, UserDto, UserRepository

_TARGET_REQUIRED_REWARDS: Final[frozenset[PromocodeRewardType]] = frozenset(
    {PromocodeRewardType.DURATION, PromocodeRewardType.TRAFFIC, PromocodeRewardType.DEVICES}
)


class ActivatePromocodeUseCase(UseCase[ActivatePromocodeDto, PromocodeDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        promocode_repository: PromocodeRepository,
        subscription_repository: SubscriptionRepository,
        plan_repository: PlanRepository,
        settings_repository: SettingsRepository,
        user_repository: UserRepository,
        purchase_subscription_use_case: PurchaseSubscriptionUseCase,
        grant_addon_use_case: GrantAddOnUseCase,
        referral_repository: ReferralRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._promocode_repository = promocode_repository
        self._subscription_repository = subscription_repository
        self._plan_repository = plan_repository
        self._settings_repository = settings_repository
        self._user_repository = user_repository
        self._purchase_subscription_use_case = purchase_subscription_use_case
        self._grant_addon_use_case = grant_addon_use_case
        self._referral_repository = referral_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: UserDto, data: ActivatePromocodeDto) -> PromocodeDto:
        code = data.code.strip().upper()
        promo = await self._promocode_repository.get_by_code(code)
        if promo is None or not promo.is_active:
            raise NotFoundError(f"Promocode '{code}' not found")

        if promo.expires_at is not None and datetime_now() > promo.expires_at:
            raise ValidationError(f"Promocode '{code}' has expired")

        await assert_available_to(promo, actor, self._subscription_repository)

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
            await self._check_subscription_cap(actor)

        async with self._uow:
            await self._promocode_repository.claim_activation(
                promocode_id=promo.id,
                user_id=actor.id,
                subscription_id=target.id if target is not None else None,
            )

        await self._apply_reward(actor, promo, target)

        async with self._uow:
            await self._event_publisher.publish(
                PromocodeActivatedEvent(
                    user=actor, promocode_id=promo.id, reward_type=promo.reward_type.value
                )
            )

        logger.info(f"{actor.log} Activated promocode '{promo.code}'")
        return promo

    async def _check_subscription_cap(self, actor: UserDto) -> None:
        shop_settings = await self._settings_repository.get_shop_settings()
        max_active = shop_settings.max_active_subscriptions
        if max_active is None:
            return
        active = await self._subscription_repository.get_active_by_user(actor.id)
        if len(active) >= max_active:
            raise ValidationError(
                f"User '{actor.id}' is already at the concurrent-subscription cap"
            )

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
                        # RENEW never rebuilds the subscription's own
                        # plan_snapshot column (see _renew()) -- reusing the
                        # target's existing snapshot is only used for the
                        # "same plan" identity check via .plan_id.
                        plan_snapshot=target.plan_snapshot,
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
                plan = await self._plan_repository.get_by_id(promo.reward_plan_id)
                # Same purchasability gate a direct checkout applies -- a
                # promocode grants a plan, it doesn't bypass whether that
                # plan is still active/available to this actor.
                has_purchase_history = await self._subscription_repository.has_any_subscription(
                    actor.id, include_trial=False
                )
                has_referrer = await self._referral_repository.has_referrer(actor.id)
                if not is_plan_purchasable_by(
                    plan,
                    actor,
                    has_purchase_history=has_purchase_history,
                    has_referrer=has_referrer,
                ):
                    raise ValidationError(f"Plan '{plan.id}' is not available for purchase")
                await self._purchase_subscription_use_case(
                    actor,
                    PurchaseSubscriptionDto(
                        user_id=actor.id,
                        plan_snapshot=PlanSnapshot(
                            plan_id=plan.id,
                            public_code=plan.public_code,
                            name=plan.name,
                            price_paid=Decimal(0),
                            currency=Currency.USD,
                            duration_days=promo.reward_duration_days,
                            traffic_limit=plan.traffic_limit,
                            device_limit=plan.device_limit,
                            traffic_limit_strategy=plan.traffic_limit_strategy,
                            is_trial=plan.is_trial,
                            internal_squads=plan.internal_squads,
                            external_squad=plan.external_squad,
                        ),
                        duration_days=promo.reward_duration_days,
                        price_paid=Decimal(0),
                        currency=Currency.USD,
                        purchase_type=PurchaseType.NEW,
                    ),
                )
            elif promo.reward_type is PromocodeRewardType.PERSONAL_DISCOUNT:
                if promo.reward:
                    async with self._uow:
                        await self._user_repository.update_fields(
                            actor.id, UpdateUserDto(personal_discount=promo.reward)
                        )
            elif promo.reward_type is PromocodeRewardType.PURCHASE_DISCOUNT:
                if promo.reward:
                    async with self._uow:
                        await self._user_repository.update_fields(
                            actor.id, UpdateUserDto(purchase_discount=promo.reward)
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
