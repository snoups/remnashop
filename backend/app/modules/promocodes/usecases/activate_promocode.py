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
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.plans import PlanDto, PlanRepository
from app.modules.promocodes.availability import (
    assert_available_to,
    assert_subscription_reward_grantable,
)
from app.modules.promocodes.dto import ActivatePromocodeDto, PromocodeDto
from app.modules.promocodes.events import PromocodeActivatedEvent
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.referrals import ReferralRepository
from app.modules.settings import SettingsRepository
from app.modules.subscriptions import (
    PlanSnapshot,
    PurchaseSubscriptionDto,
    PurchaseSubscriptionUseCase,
    SubscriptionDto,
    SubscriptionRepository,
    grant_addon_task,
)
from app.modules.users import UpdateUserDto, UserDto, UserRepository

_TARGET_REQUIRED_REWARDS: Final[frozenset[PromocodeRewardType]] = frozenset(
    {PromocodeRewardType.DURATION, PromocodeRewardType.TRAFFIC, PromocodeRewardType.DEVICES}
)


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
        settings_repository: SettingsRepository,
        user_repository: UserRepository,
        purchase_subscription_use_case: PurchaseSubscriptionUseCase,
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
        self._referral_repository = referral_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: UserDto, data: ActivatePromocodeDto) -> PromocodeDto:
        async with self._uow:
            code = data.code.strip().upper()
            promo = await self._promocode_repository.get_by_code(code)
            if promo is None or not promo.is_active:
                raise NotFoundError(
                    f"Promocode '{code}' not found", code=ErrorCode.PROMOCODE_NOT_FOUND
                )

            if promo.expires_at is not None and datetime_now() > promo.expires_at:
                raise ValidationError(
                    f"Promocode '{code}' has expired", code=ErrorCode.PROMOCODE_EXPIRED
                )

        await assert_available_to(promo, actor, self._subscription_repository)

        target: Optional[SubscriptionDto] = None
        reward_plan: Optional[PlanDto] = None
        if promo.reward_type in _TARGET_REQUIRED_REWARDS:
            if data.target_subscription_id is None:
                raise ValidationError(
                    "target_subscription_id is required for this promocode",
                    code=ErrorCode.TARGET_SUBSCRIPTION_REQUIRED,
                )
            async with self._uow:
                try:
                    target = await self._subscription_repository.get_by_id(
                        data.target_subscription_id
                    )
                except NotFoundError as error:
                    raise ValidationError(
                        "target_subscription_id does not belong to this user",
                        code=ErrorCode.TARGET_SUBSCRIPTION_NOT_OWNED,
                    ) from error
            if target.user_id != actor.id:
                raise ValidationError(
                    "target_subscription_id does not belong to this user",
                    code=ErrorCode.TARGET_SUBSCRIPTION_NOT_OWNED,
                )
            if target.status is not SubscriptionStatus.ACTIVE:
                raise ValidationError(
                    "target_subscription_id must be an active subscription",
                    code=ErrorCode.TARGET_SUBSCRIPTION_NOT_ACTIVE,
                )
        elif promo.reward_type is PromocodeRewardType.SUBSCRIPTION:
            reward_plan = await assert_subscription_reward_grantable(
                promo,
                actor,
                self._plan_repository,
                self._subscription_repository,
                self._referral_repository,
                self._settings_repository,
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

    async def _apply_reward(
        self,
        actor: UserDto,
        promo: PromocodeDto,
        target: Optional[SubscriptionDto],
        reward_plan: Optional[PlanDto],
        activation_id: int,
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
                # Dispatched, not applied inline: granting writes the
                # entitlement and then pushes the new limit to the panel, and
                # a panel failure in between leaves the two out of step with
                # the code already spent. The task retries, and its key makes
                # a redelivery land once.
                await grant_addon_task.kiq(  # type: ignore[call-overload]
                    subscription_id=target.id,
                    addon_id=promo.reward_addon_id,
                    idempotency_key=_addon_grant_key(activation_id),
                )
            elif promo.reward_type is PromocodeRewardType.SUBSCRIPTION:
                assert reward_plan is not None
                assert promo.reward_duration_days is not None
                plan = reward_plan
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
                            actor.id,
                            UpdateUserDto(
                                personal_discount=promo.reward,
                                personal_discount_promocode_id=promo.id,
                            ),
                        )
            elif promo.reward_type is PromocodeRewardType.PURCHASE_DISCOUNT:
                if promo.reward:
                    async with self._uow:
                        await self._user_repository.update_fields(
                            actor.id,
                            UpdateUserDto(
                                purchase_discount=promo.reward,
                                purchase_discount_promocode_id=promo.id,
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
