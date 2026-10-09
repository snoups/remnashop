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
from app.modules.users import TelegramUserRegisteredEvent


async def _kick_rewards(entry: StoredEvent, *, is_new_purchase: bool) -> None:
    payment_key = entry.payload.get("payment_key")
    if not payment_key:
        return  # trial/promocode/referral grant; only paid orders earn a reward

    await assign_referral_rewards_task.kiq(  # type: ignore[call-overload]
        user_id=entry.payload["user"]["id"],
        subscription_id=entry.payload["subscription_id"],
        is_new_purchase=is_new_purchase,
        payment_key=payment_key,
    )


async def _on_subscription_purchased(entry: StoredEvent) -> None:
    await _kick_rewards(entry, is_new_purchase=True)


async def _on_subscription_renewed_or_changed(entry: StoredEvent) -> None:
    await _kick_rewards(entry, is_new_purchase=False)


async def _on_telegram_user_registered(entry: StoredEvent) -> None:
    referral_code = entry.payload.get("referral_code")
    if not referral_code:
        return

    await attach_referral_on_registration_task.kiq(  # type: ignore[call-overload]
        user_id=entry.payload["user"]["id"], referral_code=referral_code
    )


async def _on_transaction_refunded(entry: StoredEvent) -> None:
    payment_key = entry.payload.get("payment_key")
    if not payment_key:
        return  # outbox rows written before the field existed

    await reverse_referral_rewards_task.kiq(payment_key=payment_key)  # type: ignore[call-overload]


def register_subscribers(bus: EventBus) -> None:
    bus.subscribe(TelegramUserRegisteredEvent, _on_telegram_user_registered)
    bus.subscribe(SubscriptionPurchasedEvent, _on_subscription_purchased)
    bus.subscribe(SubscriptionRenewedEvent, _on_subscription_renewed_or_changed)
    bus.subscribe(SubscriptionChangedEvent, _on_subscription_renewed_or_changed)
    bus.subscribe(TransactionRefundedEvent, _on_transaction_refunded)
