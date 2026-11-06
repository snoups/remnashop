from collections.abc import Sequence
from typing import Optional

from app.core.actor import Actor
from app.core.enums import SubscriptionStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.utils.time import datetime_now
from app.modules.plans import PlanDto, is_plan_purchasable_by
from app.modules.settings import SettingsRepository
from app.modules.subscriptions.dto import SubscriptionDto
from app.modules.subscriptions.ports import OpenOrderCounter, ReferrerLookup
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserDto, UserRepository, visible_user


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
        # an EXPIRED subscription holds its slot too: it's renewed in place, not bought over
        if lock:
            owned = await self._subscription_repository.get_live_by_user_for_update(user_id)
        else:
            owned = await self._subscription_repository.get_live_by_user(user_id)
        # a NEW purchase upgrades an active trial in place, so the trial holds no slot
        paid = [subscription for subscription in owned if not subscription.is_trial]
        if len(paid) + pending >= max_active:
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

    async def renewable(
        self, plans: Sequence[PlanDto], user_id: int, subscription_id: int
    ) -> list[PlanDto]:
        # availability decides who may buy a plan, not who may keep it:
        # switching the plan off is what stops its renewals
        target = await get_owned_target(self._subscription_repository, subscription_id, user_id)
        return [
            plan for plan in plans if plan.is_active and plan.id == target.plan_snapshot.plan_id
        ]


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


def _hidden(subscription_id: int) -> NotFoundError:
    return NotFoundError(
        f"Subscription '{subscription_id}' not found", code=ErrorCode.SUBSCRIPTION_NOT_FOUND
    )


async def get_visible_subscription(
    repository: SubscriptionRepository,
    user_repository: UserRepository,
    actor: Actor,
    subscription_id: int,
) -> SubscriptionDto:
    # a hidden staff member's subscription answers like a missing one: its url
    # is that person's VPN access
    subscription = await repository.get_by_id(subscription_id)
    owner = await user_repository.find_by_id(subscription.user_id)
    if owner is not None and visible_user(actor, owner) is None:
        raise _hidden(subscription_id)
    return subscription


async def get_manageable_subscription(
    repository: SubscriptionRepository,
    user_repository: UserRepository,
    actor: Actor,
    subscription_id: int,
    *,
    for_read: bool = False,
) -> SubscriptionDto:
    """A live subscription the actor may change: staff ones only from a higher
    role, the actor's own with STAFF_SELF_MANAGE unless it is only read."""
    subscription = await get_visible_subscription(
        repository, user_repository, actor, subscription_id
    )
    owner = await user_repository.find_by_id(subscription.user_id)
    if owner is not None and owner.id == actor.id:
        if not for_read and not PermissionPolicy.has_permission(
            actor, Permission.STAFF_SELF_MANAGE
        ):
            raise PermissionDeniedError
    elif owner is not None and not PermissionPolicy.can_manage(actor, owner):
        raise _hidden(subscription_id)
    if subscription.status is SubscriptionStatus.DELETED:
        raise ValidationError(
            f"Subscription '{subscription_id}' is deleted", code=ErrorCode.SUBSCRIPTION_DELETED
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
