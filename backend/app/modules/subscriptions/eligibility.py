from collections.abc import Sequence

from app.core.actor import Actor
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import ReferrerLookup
from app.modules.plans import PlanDto, is_plan_purchasable_by
from app.modules.settings import SettingsRepository
from app.modules.subscriptions.repository import SubscriptionRepository


class PurchaseEligibility:
    """What a user may buy: the concurrent-subscription cap and plan
    availability, shared by the catalog, trial, checkout, promocode rewards and
    the purchase itself so none of them can disagree. Reads only -- callers
    run it inside their own unit of work."""

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        referrer_lookup: ReferrerLookup,
        settings_repository: SettingsRepository,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._referrer_lookup = referrer_lookup
        self._settings_repository = settings_repository

    async def assert_below_cap(self, user_id: int, *, lock: bool = False) -> None:
        # lock=True only under the caller's purchase-cap advisory lock
        max_active = (await self._settings_repository.get_shop_settings()).max_active_subscriptions
        if max_active is None:
            return
        if lock:
            active = await self._subscription_repository.get_active_by_user_for_update(user_id)
        else:
            active = await self._subscription_repository.get_active_by_user(user_id)
        if len(active) >= max_active:
            raise ValidationError(
                f"User '{user_id}' is already at the concurrent-subscription cap",
                code=ErrorCode.SUBSCRIPTION_LIMIT_REACHED,
            )

    async def purchasable(self, plans: Sequence[PlanDto], user: Actor) -> list[PlanDto]:
        if not plans:
            return []
        has_purchase_history = await self._subscription_repository.has_any_subscription(
            user.id, include_trial=False
        )
        has_referrer = await self._referrer_lookup.has_referrer(user.id)
        return [
            plan
            for plan in plans
            if is_plan_purchasable_by(
                plan, user, has_purchase_history=has_purchase_history, has_referrer=has_referrer
            )
        ]

    async def is_purchasable(self, plan: PlanDto, user: Actor) -> bool:
        return bool(await self.purchasable([plan], user))
