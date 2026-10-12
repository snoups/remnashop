from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.core.events import EventCategory, StoredEvent
from app.core.utils.time import datetime_now
from app.modules.customer_notifications import subscribers

_KIQ = "app.modules.customer_notifications.tasks.notify_customer_task.kiq"


def _entry(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        outbox_id=5,
        category=EventCategory.SUBSCRIPTION,
        event_type=event_type,
        occurred_at=datetime_now(),
        payload=payload,
        actor_id=None,
        actor_login=None,
        actor_name=None,
        actor_email=None,
        ip_address=None,
    )


@pytest.mark.parametrize(
    ("handler", "event_type", "payload", "user_id", "args"),
    [
        (subscribers._on_purchase, "SubscriptionPurchasedEvent", {"user": {"id": 7}}, 7, {}),
        (subscribers._on_purchase, "SubscriptionChangedEvent", {"user": {"id": 7}}, 7, {}),
        (
            subscribers._on_renewed,
            "SubscriptionRenewedEvent",
            {"user": {"id": 7}, "duration_days": 30},
            7,
            {"duration_days": 30},
        ),
        (
            subscribers._on_addon,
            "SubscriptionAddOnGrantedEvent",
            {"user": {"id": 0}, "target": {"id": 9}},
            9,
            {},
        ),
        (
            subscribers._on_addon,
            "SubscriptionAddOnGrantedEvent",
            {"user": {"id": 7}, "target": None},
            7,
            {},
        ),
        (
            subscribers._on_granted,
            "SubscriptionGrantedEvent",
            {"target": {"id": 9}, "duration_days": 5},
            9,
            {"duration_days": 5},
        ),
        (
            subscribers._on_refund,
            "TransactionRefundedEvent",
            {"user_id": 3, "amount": "10.00", "currency": "USD"},
            3,
            {"amount": "10.00", "currency": "USD"},
        ),
        (
            subscribers._on_refund,
            "TransactionPartiallyRefundedEvent",
            {"user_id": 3, "amount": "1.00", "currency": "USD"},
            3,
            {"amount": "1.00", "currency": "USD"},
        ),
        (
            subscribers._on_reward,
            "ReferralRewardIssuedEvent",
            {"user": {"id": 7}, "level": 1, "reward_type": "EXTRA_DAYS", "amount": "5"},
            7,
            {"reward_type": "EXTRA_DAYS", "amount": 5},
        ),
        (
            subscribers._on_reward,
            "ReferralRewardIssuedEvent",
            {"user": {"id": 7}, "level": 2, "reward_type": "POINTS", "amount": "12.50"},
            7,
            {"reward_type": "POINTS", "amount": "12.50"},
        ),
        (
            subscribers._on_reward,
            "InviteeRewardIssuedEvent",
            {"user": {"id": 7}, "reward_type": "EXTRA_DAYS", "amount": 3},
            7,
            {"reward_type": "EXTRA_DAYS", "amount": 3},
        ),
    ],
)
async def test_event_enqueues_notification(
    handler: Any, event_type: str, payload: dict[str, Any], user_id: int, args: dict[str, Any]
) -> None:
    with patch(_KIQ, new_callable=AsyncMock) as kiq:
        await handler(_entry(event_type, payload))

    kiq.assert_awaited_once_with(user_id=user_id, event_type=event_type, outbox_id=5, args=args)


async def test_system_actor_owner_is_skipped() -> None:
    with patch(_KIQ, new_callable=AsyncMock) as kiq:
        await subscribers._on_purchase(_entry("SubscriptionPurchasedEvent", {"user": {"id": 0}}))

    kiq.assert_not_awaited()
