from dataclasses import dataclass
from typing import ClassVar

from app.core.event_bus import EventBus
from app.core.events import ActorTargetEvent, EventCategory, StoredEvent, UserEvent
from app.modules.subscriptions.events import SubscriptionPurchasedEvent, SubscriptionRenewedEvent


@dataclass(frozen=True, kw_only=True)
class ReferralAttachedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.REFERRAL
    referrer_id: int


@dataclass(frozen=True, kw_only=True)
class ReferralRewardIssuedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.REFERRAL
    level: int
    reward_type: str
    amount: str


@dataclass(frozen=True, kw_only=True)
class PointsWithdrawalRequestedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.REFERRAL
    amount: str


@dataclass(frozen=True, kw_only=True)
class UserPointsAdjustedEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.REFERRAL
    delta: str


async def _on_subscription_purchased(entry: StoredEvent) -> None:
    from app.modules.referrals.tasks import assign_referral_rewards_task  # noqa: PLC0415

    await assign_referral_rewards_task.kiq(  # type: ignore[call-overload]
        user_id=entry.payload["user"]["id"],
        subscription_id=entry.payload["subscription_id"],
        is_new_purchase=True,
    )


async def _on_subscription_renewed(entry: StoredEvent) -> None:
    from app.modules.referrals.tasks import assign_referral_rewards_task  # noqa: PLC0415

    await assign_referral_rewards_task.kiq(  # type: ignore[call-overload]
        user_id=entry.payload["user"]["id"],
        subscription_id=entry.payload["subscription_id"],
        is_new_purchase=False,
    )


def register_subscribers(bus: EventBus) -> None:
    bus.subscribe(SubscriptionPurchasedEvent, _on_subscription_purchased)
    bus.subscribe(SubscriptionRenewedEvent, _on_subscription_renewed)
