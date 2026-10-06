from decimal import Decimal
from typing import Optional

from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.enums import (
    Currency,
    PromocodeRewardType,
    PurchaseType,
    SubscriptionStatus,
)
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans import PlanDto, PlanRepository
from app.modules.promocodes.availability import (
    assert_available_to,
    assert_subscription_reward_grantable,
    get_usable_promocode,
)
from app.modules.promocodes.dto import ActivatePromocodeDto, PromocodeDto
from app.modules.promocodes.events import PromocodeActivatedEvent
from app.modules.promocodes.plan_limits import PLAN_LIMITED_REWARDS
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.subscriptions import (
    GrantAddOnDispatch,
    PlanSnapshot,
    PurchaseEligibility,
    PurchaseSubscriptionDto,
    PurchaseSubscriptionUseCase,
    SubscriptionDto,
    SubscriptionRepository,
    get_owned_target,
)
from app.modules.users import UpdateUserDto, UserDto, UserRepository


def _addon_grant_key(activation_id: int) -> str:
    # Keyed on the activation, not on (promocode, user): a reusable code is
    # activated more than once by the same person, and each of those
    # activations earns its own grant.
    return f"promocode-activation:{activation_id}"


class ActivatePromocodeUseCase(UseCase[ActivatePromocodeDto, PromocodeDto, UserDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        promocode_repository: PromocodeRepository,
        subscription_repository: SubscriptionRepository,
        plan_repository: PlanRepository,
        eligibility: PurchaseEligibility,
        user_repository: UserRepository,
        purchase_subscription_use_case: PurchaseSubscriptionUseCase,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
        grant_addon_dispatch: GrantAddOnDispatch,
    ) -> None:
        self._promocode_repository = promocode_repository
        self._subscription_repository = subscription_repository
        self._plan_repository = plan_repository
        self._eligibility = eligibility
        self._user_repository = user_repository
        self._purchase_subscription_use_case = purchase_subscription_use_case
        self._uow = uow
        self._event_publisher = event_publisher
        self._grant_addon_dispatch = grant_addon_dispatch

    async def _execute(self, actor: UserDto, data: ActivatePromocodeDto) -> PromocodeDto:
        async with self._uow:
            promo = await get_usable_promocode(self._promocode_repository, data.code)

        await assert_available_to(promo, actor, self._subscription_repository)

        target: Optional[SubscriptionDto] = None
        reward_plan: Optional[PlanDto] = None
        if promo.reward_type in PLAN_LIMITED_REWARDS:
            if data.target_subscription_id is None:
                raise ValidationError(
                    "target_subscription_id is required for this promocode",
                    code=ErrorCode.TARGET_SUBSCRIPTION_REQUIRED,
                )
            async with self._uow:
                target = await get_owned_target(
                    self._subscription_repository, data.target_subscription_id, actor.id
                )
            if target.status is not SubscriptionStatus.ACTIVE:
                raise ValidationError(
                    "target_subscription_id must be an active subscription",
                    code=ErrorCode.TARGET_SUBSCRIPTION_NOT_ACTIVE,
                )
            await self._assert_plan_accepts(promo, target)
        elif promo.reward_type is PromocodeRewardType.SUBSCRIPTION:
            reward_plan = await assert_subscription_reward_grantable(
                promo,
                actor,
                self._plan_repository,
                self._eligibility,
            )

        async with self._uow:
            activation = await self._promocode_repository.claim_activation(
                promocode_id=promo.id,
                user_id=actor.id,
                subscription_id=target.id if target is not None else None,
            )

        await self._apply_reward(actor, promo, target, reward_plan, activation.id)

        async with self._uow:
            await self._event_publisher.publish(
                PromocodeActivatedEvent(
                    user=actor, promocode_id=promo.id, reward_type=promo.reward_type.value
                )
            )

        logger.info(f"{actor.log} Activated promocode '{promo.code}'")
        return promo

    async def _assert_plan_accepts(self, promo: PromocodeDto, target: SubscriptionDto) -> None:
        plan_id = target.plan_snapshot.plan_id
        if promo.allowed_plan_ids and plan_id not in promo.allowed_plan_ids:
            raise ValidationError(
                "This promocode isn't valid for the subscription's plan",
                code=ErrorCode.PROMOCODE_PLAN_NOT_ALLOWED,
            )
        async with self._uow:
            try:
                plan = await self._plan_repository.get_by_id(plan_id)
            except NotFoundError:
                return  # a deleted plan keeps the defaults: allowed
        if not plan.allow_promocodes:
            raise ValidationError(
                "The subscription's plan doesn't accept promocodes",
                code=ErrorCode.PROMOCODE_PLAN_NOT_ALLOWED,
            )

    async def _apply_reward(
        self,
        actor: UserDto,
        promo: PromocodeDto,
        target: Optional[SubscriptionDto],
        reward_plan: Optional[PlanDto],
        activation_id: int,
    ) -> None:
        try:
            reward_type = promo.reward_type
            if reward_type is PromocodeRewardType.DURATION:
                assert target is not None
                await self._extend_subscription(actor, promo, target)
            elif reward_type in (PromocodeRewardType.TRAFFIC, PromocodeRewardType.DEVICES):
                assert target is not None
                await self._grant_addon(promo, target, activation_id)
            elif reward_type is PromocodeRewardType.SUBSCRIPTION:
                assert reward_plan is not None
                await self._grant_subscription(actor, promo, reward_plan)
            elif reward_type is PromocodeRewardType.PERSONAL_DISCOUNT and promo.reward:
                await self._set_discount(
                    actor,
                    UpdateUserDto(
                        personal_discount=promo.reward, personal_discount_promocode_id=promo.id
                    ),
                )
            elif reward_type is PromocodeRewardType.PURCHASE_DISCOUNT and promo.reward:
                await self._set_discount(
                    actor,
                    UpdateUserDto(
                        purchase_discount=promo.reward, purchase_discount_promocode_id=promo.id
                    ),
                )
        except Exception:
            # the claim is already committed: the worst case is an activation
            # with no reward, never a grant past the limit (the same accepted
            # dual-write risk as GrantAddOnUseCase)
            logger.error(
                f"{actor.log} Promocode '{promo.code}' activation recorded but reward "
                f"application failed -- possible orphaned activation"
            )
            raise

    async def _extend_subscription(
        self, actor: UserDto, promo: PromocodeDto, target: SubscriptionDto
    ) -> None:
        assert promo.reward is not None
        await self._purchase_subscription_use_case(
            actor,
            PurchaseSubscriptionDto(
                user_id=actor.id,
                # RENEW never rebuilds plan_snapshot (RenewPurchase); the
                # target's snapshot only feeds the same-plan check via .plan_id
                plan_snapshot=target.plan_snapshot,
                duration_days=promo.reward,
                price_paid=Decimal(0),
                currency=Currency.USD,
                purchase_type=PurchaseType.RENEW,
                target_subscription_id=target.id,
            ),
        )

    async def _grant_addon(
        self, promo: PromocodeDto, target: SubscriptionDto, activation_id: int
    ) -> None:
        assert promo.reward_addon_id is not None
        # Dispatched, not applied inline: granting writes the entitlement and
        # then pushes the new limit to the panel, and a panel failure in
        # between leaves the two out of step with the code already spent. The
        # task retries, and its key makes a redelivery land once.
        await self._grant_addon_dispatch.kiq(
            subscription_id=target.id,
            addon_id=promo.reward_addon_id,
            idempotency_key=_addon_grant_key(activation_id),
        )

    async def _grant_subscription(self, actor: UserDto, promo: PromocodeDto, plan: PlanDto) -> None:
        assert promo.reward_duration_days is not None
        await self._purchase_subscription_use_case(
            actor,
            PurchaseSubscriptionDto(
                user_id=actor.id,
                plan_snapshot=PlanSnapshot.from_plan(
                    plan,
                    price_paid=Decimal(0),
                    currency=Currency.USD,
                    duration_days=promo.reward_duration_days,
                ),
                duration_days=promo.reward_duration_days,
                price_paid=Decimal(0),
                currency=Currency.USD,
                purchase_type=PurchaseType.NEW,
            ),
        )

    async def _set_discount(self, actor: UserDto, update: UpdateUserDto) -> None:
        async with self._uow:
            await self._user_repository.update_fields(actor.id, update)
