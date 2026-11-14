from datetime import datetime
from typing import Optional

from app.core.constants import GB_TO_BYTES
from app.core.db.uow import UnitOfWork
from app.core.enums import PromocodeRewardType, SubscriptionStatus
from app.core.exceptions import NotFoundError
from app.core.utils.time import datetime_now
from app.modules.plans import AddOnRepository, PlanRepository
from app.modules.promocodes.dto import PromocodeDto
from app.modules.subscriptions import PanelTrafficUsage, SubscriptionDto, traffic_spent_for_good


def reward_takes_effect(
    subscription: SubscriptionDto,
    reward_type: PromocodeRewardType,
    *,
    used_traffic: Optional[int],
    extra_traffic_gb: int,
    now: datetime,
) -> bool:
    """Whether the reward is of any use to the subscription. ACTIVE takes any;
    days help EXPIRED or LIMITED unless the traffic is spent for good; traffic
    helps LIMITED while its term runs. Never a trial; unknown usage is no."""
    if subscription.is_trial:
        return False
    # days add nothing to a term that never ends
    if reward_type is PromocodeRewardType.DURATION and subscription.is_unlimited:
        return False
    if subscription.status is SubscriptionStatus.ACTIVE:
        return True
    if used_traffic is None or subscription.status not in (
        SubscriptionStatus.EXPIRED,
        SubscriptionStatus.LIMITED,
    ):
        return False
    if reward_type is PromocodeRewardType.DURATION:
        return not traffic_spent_for_good(subscription, used_traffic)
    if reward_type is PromocodeRewardType.TRAFFIC:
        limit = (subscription.effective_traffic_limit + extra_traffic_gb) * GB_TO_BYTES
        return (
            subscription.status is SubscriptionStatus.LIMITED
            and subscription.expire_at > now
            and used_traffic < limit
        )
    return False


class PromocodeTargets:
    """Which subscription a promocode's reward may go to: shared by the
    activation and the list a customer picks from, so the list never offers
    one the activation then refuses."""

    def __init__(
        self,
        plan_repository: PlanRepository,
        addon_repository: AddOnRepository,
        usage: PanelTrafficUsage,
        uow: UnitOfWork,
    ) -> None:
        self._plan_repository = plan_repository
        self._addon_repository = addon_repository
        self._usage = usage
        self._uow = uow

    async def takes_reward(self, promo: PromocodeDto, subscription: SubscriptionDto) -> bool:
        needs_usage = (
            not subscription.is_trial and subscription.status is not SubscriptionStatus.ACTIVE
        )
        return reward_takes_effect(
            subscription,
            promo.reward_type,
            used_traffic=await self._usage.used_traffic(subscription) if needs_usage else None,
            extra_traffic_gb=await self._extra_traffic_gb(promo),
            now=datetime_now(),
        )

    async def plan_accepts(self, promo: PromocodeDto, subscription: SubscriptionDto) -> bool:
        plan_id = subscription.plan_snapshot.plan_id
        if promo.allowed_plan_ids and plan_id not in promo.allowed_plan_ids:
            return False
        async with self._uow:
            try:
                plan = await self._plan_repository.get_by_id(plan_id)
            except NotFoundError:
                return True  # a deleted plan keeps the defaults: allowed
        return plan.allow_promocodes

    async def _extra_traffic_gb(self, promo: PromocodeDto) -> int:
        if promo.reward_type is not PromocodeRewardType.TRAFFIC or promo.reward_addon_id is None:
            return 0
        async with self._uow:
            addon = await self._addon_repository.get_by_id(promo.reward_addon_id)
        return addon.amount
