from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

from app.core.enums import Currency, SubscriptionStatus
from app.core.utils.time import datetime_now
from app.modules.subscriptions.dto import CreateSubscriptionDto, PlanSnapshot, SubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


def make_plan_snapshot(**overrides: Any) -> PlanSnapshot:
    """Placeholder PlanSnapshot for tests that don't assert on its contents
    -- override any field (e.g. plan_id=7) to assert on it."""
    defaults: dict[str, Any] = {
        "plan_id": 1,
        "public_code": "basic",
        "name": "Basic",
        "price_paid": Decimal("0"),
        "currency": Currency.RUB,
        "duration_days": 30,
    }
    defaults.update(overrides)
    return PlanSnapshot(**defaults)


async def create_subscription(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    *,
    telegram_id: int,
    remnawave_user_id: int,
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
    expire_at: Optional[datetime] = None,
    **snapshot_overrides: Any,
) -> SubscriptionDto:
    """Creates a user and a subscription for it in one call. `telegram_id`
    and `remnawave_user_id` must be unique per test (both columns are
    unique) -- callers pick distinct literal values, matching this test
    suite's existing convention of per-test literal IDs."""
    user = await user_repository.create(CreateUserDto(name="buyer", telegram_id=telegram_id))
    return await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=user.id,
            remnawave_user_id=remnawave_user_id,
            status=status,
            traffic_limit=100,
            device_limit=3,
            expire_at=expire_at or (datetime_now() + timedelta(days=30)),
            url=f"https://example.com/sub/{remnawave_user_id}",
            plan_snapshot=make_plan_snapshot(**snapshot_overrides),
        )
    )
