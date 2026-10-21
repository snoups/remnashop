from typing import Union

from app.core.event_bus import EventBus
from app.core.events import StoredEvent
from app.modules.referrals.tasks import (
    assign_referral_rewards_task,
    attach_referral_on_registration_task,
    reverse_referral_rewards_task,
)
from app.modules.subscriptions import (
    SubscriptionChangedEvent,
    SubscriptionPurchasedEvent,
    SubscriptionRenewedEvent,
)
from app.modules.transactions import TransactionRefundedEvent
from app.modules.users import CabinetUserRegisteredEvent, TelegramUserRegisteredEvent

_PaidEvent = Union[SubscriptionPurchasedEvent, SubscriptionRenewedEvent, SubscriptionChangedEvent]


async def _kick_rewards(event: _PaidEvent, *, is_new_purchase: bool) -> None:
    if not event.payment_key:
        return  # trial/promocode/referral grant; only paid orders earn a reward

    await assign_referral_rewards_task.kiq(  # type: ignore[call-overload]
        user_id=event.user.id,
        subscription_id=event.subscription_id,
        is_new_purchase=is_new_purchase,
        payment_key=event.payment_key,
    )


async def _on_subscription_purchased(event: SubscriptionPurchasedEvent, entry: StoredEvent) -> None:
    await _kick_rewards(event, is_new_purchase=True)


async def _on_subscription_renewed_or_changed(
    event: Union[SubscriptionRenewedEvent, SubscriptionChangedEvent], entry: StoredEvent
) -> None:
    await _kick_rewards(event, is_new_purchase=False)


async def _on_user_registered(
    event: Union[TelegramUserRegisteredEvent, CabinetUserRegisteredEvent], entry: StoredEvent
) -> None:
    if not event.referral_code:
        return

    await attach_referral_on_registration_task.kiq(  # type: ignore[call-overload]
        user_id=event.user.id, referral_code=event.referral_code
    )


async def _on_transaction_refunded(event: TransactionRefundedEvent, entry: StoredEvent) -> None:
    if not event.payment_key:
        return

    await reverse_referral_rewards_task.kiq(payment_key=event.payment_key)  # type: ignore[call-overload]


def register_subscribers(bus: EventBus) -> None:
    bus.subscribe(TelegramUserRegisteredEvent, _on_user_registered)
    bus.subscribe(CabinetUserRegisteredEvent, _on_user_registered)
    bus.subscribe(SubscriptionPurchasedEvent, _on_subscription_purchased)
    bus.subscribe(SubscriptionRenewedEvent, _on_subscription_renewed_or_changed)
    bus.subscribe(SubscriptionChangedEvent, _on_subscription_renewed_or_changed)
    bus.subscribe(TransactionRefundedEvent, _on_transaction_refunded)
