from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

from remnapy.enums import TrafficLimitStrategy
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Currency, SubscriptionStatus
from app.core.utils.time import datetime_now
from app.modules.plans.dto import PlanDto
from app.modules.referrals.repository import ReferralRepository
from app.modules.settings.repository import SettingsRepository
from app.modules.subscriptions.dto import CreateSubscriptionDto, PlanSnapshot, SubscriptionDto
from app.modules.subscriptions.eligibility import PurchaseEligibility
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.transactions.repository import TransactionRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


def make_eligibility(session: AsyncSession) -> PurchaseEligibility:
    return PurchaseEligibility(
        SubscriptionRepository(session),
        ReferralRepository(session),
        SettingsRepository(session),
        TransactionRepository(session),
        UserRepository(session),
    )


def make_plan_snapshot(**overrides: Any) -> PlanSnapshot:
    """Placeholder PlanSnapshot; override a field (e.g. plan_id=7) to assert
    on it."""
    defaults: dict[str, Any] = {
        "plan_id": 1,
        "public_code": "basic",
        "name": "Basic",
        "price_paid": Decimal("0"),
        "currency": Currency.RUB,
        "duration_days": 30,
        "traffic_limit": 100,
        "device_limit": 3,
        "traffic_limit_strategy": TrafficLimitStrategy.NO_RESET,
        "is_trial": False,
        "internal_squads": [],
        "external_squad": None,
    }
    defaults.update(overrides)
    return PlanSnapshot(**defaults)


def snapshot_from_plan(plan: PlanDto, **overrides: Any) -> PlanSnapshot:
    """Builds the PlanSnapshot a real checkout/promocode-redemption path would
    build for a live plan, for tests that purchase against a plan they just
    created via PlanRepository and need the operational fields to match it."""
    defaults: dict[str, Any] = {
        "plan_id": plan.id,
        "public_code": plan.public_code,
        "name": plan.name,
        "price_paid": Decimal("0"),
        "currency": Currency.RUB,
        "duration_days": 30,
        "traffic_limit": plan.traffic_limit,
        "device_limit": plan.device_limit,
        "traffic_limit_strategy": plan.traffic_limit_strategy,
        "is_trial": plan.is_trial,
        "internal_squads": plan.internal_squads,
        "external_squad": plan.external_squad,
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
    is_trial: bool = False,
    **snapshot_overrides: Any,
) -> SubscriptionDto:
    """Creates a user and a subscription for it in one call. `telegram_id`
    and `remnawave_user_id` must be unique per test (both columns are
    unique)."""
    user = await user_repository.create(CreateUserDto(name="buyer", telegram_id=telegram_id))
    return await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=user.id,
            remnawave_user_id=remnawave_user_id,
            status=status,
            is_trial=is_trial,
            traffic_limit=100,
            device_limit=3,
            expire_at=expire_at or (datetime_now() + timedelta(days=30)),
            url=f"https://example.com/sub/{remnawave_user_id}",
            plan_snapshot=make_plan_snapshot(**snapshot_overrides),
        )
    )
