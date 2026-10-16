from collections.abc import Sequence
from typing import Optional

from app.core.actor import Actor
from app.core.enums import SubscriptionStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, ValidationError
from app.core.ports import OpenOrderCounter, ReferrerLookup
from app.core.utils.time import datetime_now
from app.modules.plans import PlanDto, is_plan_purchasable_by
from app.modules.settings import SettingsRepository
from app.modules.subscriptions.dto import SubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserDto, UserRepository


class PurchaseEligibility:
    """What a user may buy: the concurrent-subscription cap and plan
    availability, shared by the catalog, trial, checkout, promocode rewards and
    the purchase itself so none of them can disagree. Reads only; callers
    run it inside their own unit of work."""

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        referrer_lookup: ReferrerLookup,
        settings_repository: SettingsRepository,
        open_order_counter: OpenOrderCounter,
        user_repository: UserRepository,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._referrer_lookup = referrer_lookup
        self._settings_repository = settings_repository
        self._open_order_counter = open_order_counter
        self._user_repository = user_repository

    async def lock_user(self, user_id: int) -> None:
        # same key as NewPurchase, so a checkout and a fulfilment for one user serialize
        await self._subscription_repository.acquire_purchase_cap_lock(user_id)

    async def open_new_orders(self, user_id: int, *, exclude_key: Optional[str] = None) -> int:
        return await self._open_order_counter.count_open_new_orders(
            user_id, datetime_now(), exclude_key=exclude_key
        )

    async def assert_below_cap(self, user_id: int, *, lock: bool = False, pending: int = 0) -> None:
        # lock=True only under lock_user; pending = open orders not yet provisioned
        max_active = (await self._settings_repository.get_shop_settings()).max_active_subscriptions
        if max_active is None:
            return
        if lock:
            active = await self._subscription_repository.get_active_by_user_for_update(user_id)
        else:
            active = await self._subscription_repository.get_active_by_user(user_id)
        if len(active) + pending >= max_active:
            raise ValidationError(
                f"User '{user_id}' is already at the concurrent-subscription cap",
                code=ErrorCode.SUBSCRIPTION_LIMIT_REACHED,
            )

    async def purchasable(
        self, plans: Sequence[PlanDto], user: Actor, *, has_open_order: bool = False
    ) -> list[PlanDto]:
        if not plans:
            return []
        has_purchase_history = (
            has_open_order
            or await self._subscription_repository.has_any_subscription(
                user.id, include_trial=False
            )
        )
        has_referrer = await self._referrer_lookup.has_referrer(user.id)
        # read fresh, not off the actor: a trial plan is one per customer, paid or free
        trial_available = False
        if any(plan.is_trial for plan in plans):
            account = await self._user_repository.find_by_id(user.id)
            trial_available = account is not None and account.is_trial_available
        return [
            plan
            for plan in plans
            if (trial_available or not plan.is_trial)
            and is_plan_purchasable_by(
                plan, user, has_purchase_history=has_purchase_history, has_referrer=has_referrer
            )
        ]

    async def is_purchasable(
        self, plan: PlanDto, user: Actor, *, has_open_order: bool = False
    ) -> bool:
        return bool(await self.purchasable([plan], user, has_open_order=has_open_order))


async def get_owned_target(
    repository: SubscriptionRepository, subscription_id: int, user_id: int
) -> SubscriptionDto:
    # a missing subscription answers like someone else's, so ids can't be probed
    try:
        target = await repository.get_by_id(subscription_id)
    except NotFoundError as error:
        raise ValidationError(
            "target_subscription_id does not belong to this user",
            code=ErrorCode.TARGET_SUBSCRIPTION_NOT_OWNED,
        ) from error
    if target.user_id != user_id:
        raise ValidationError(
            "target_subscription_id does not belong to this user",
            code=ErrorCode.TARGET_SUBSCRIPTION_NOT_OWNED,
        )
    return target


async def get_owned_live_target(
    repository: SubscriptionRepository, subscription_id: int, user_id: int
) -> SubscriptionDto:
    target = await get_owned_target(repository, subscription_id, user_id)
    if target.status is SubscriptionStatus.DELETED:
        raise ValidationError("Subscription is deleted", code=ErrorCode.SUBSCRIPTION_DELETED)
    return target


async def get_live_subscription(
    repository: SubscriptionRepository, subscription_id: int
) -> SubscriptionDto:
    subscription = await repository.get_by_id(subscription_id)
    if subscription.status is SubscriptionStatus.DELETED:
        raise ValidationError(
            f"Subscription '{subscription_id}' is deleted", code=ErrorCode.SUBSCRIPTION_DELETED
        )
    return subscription


async def lock_live_subscription(
    repository: SubscriptionRepository, subscription_id: int
) -> SubscriptionDto:
    # re-read under the row lock after a panel call: the row may be gone by now
    subscription = await repository.get_by_id_for_update(subscription_id)
    if subscription.status is SubscriptionStatus.DELETED:
        raise ValidationError(
            f"Subscription '{subscription_id}' was deleted", code=ErrorCode.SUBSCRIPTION_DELETED
        )
    return subscription


async def subscription_owner(
    user_repository: UserRepository, subscription: SubscriptionDto
) -> UserDto:
    owner = await user_repository.find_by_id(subscription.user_id)
    if owner is None:
        raise NotFoundError(
            f"User '{subscription.user_id}' not found", code=ErrorCode.USER_NOT_FOUND
        )
    return owner
