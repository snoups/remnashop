import pytest

from app.core.enums import PlanAvailability, PlanType
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.modules.plans.dto import PlanDto
from app.modules.subscriptions.dto import CreateSubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users.repository import UserRepository
from tests.modules.subscriptions.factories import create_subscription, make_eligibility


def _plan(public_code: str, availability: PlanAvailability) -> PlanDto:
    return PlanDto(
        public_code=public_code,
        name=public_code,
        type=PlanType.BOTH,
        availability=availability,
        traffic_limit=100,
        device_limit=3,
        is_active=True,
    )


async def test_cap_counts_the_users_active_subscriptions(
    subscription_repository: SubscriptionRepository, user_repository: UserRepository
) -> None:
    eligibility = make_eligibility(subscription_repository.session)
    sub = await create_subscription(
        subscription_repository, user_repository, telegram_id=91001, remnawave_user_id=91001
    )

    await eligibility.assert_below_cap(sub.user_id)  # 1 of the default 3

    for remnawave_user_id in (91002, 91003):
        await subscription_repository.create(
            CreateSubscriptionDto(
                user_id=sub.user_id,
                remnawave_user_id=remnawave_user_id,
                status=sub.status,
                is_trial=False,
                traffic_limit=sub.traffic_limit,
                device_limit=sub.device_limit,
                expire_at=sub.expire_at,
                url=f"https://example.com/sub/{remnawave_user_id}",
                plan_snapshot=sub.plan_snapshot,
            )
        )
    with pytest.raises(ValidationError) as error:
        await eligibility.assert_below_cap(sub.user_id, lock=True)
    assert error.value.code is ErrorCode.SUBSCRIPTION_LIMIT_REACHED


async def test_purchasable_applies_purchase_history(
    subscription_repository: SubscriptionRepository, user_repository: UserRepository
) -> None:
    eligibility = make_eligibility(subscription_repository.session)
    sub = await create_subscription(
        subscription_repository, user_repository, telegram_id=91011, remnawave_user_id=91011
    )
    buyer = await user_repository.find_by_id(sub.user_id)
    assert buyer is not None
    plans = [
        _plan("for-all", PlanAvailability.ALL),
        _plan("for-new", PlanAvailability.NEW),
        _plan("for-existing", PlanAvailability.EXISTING),
    ]

    allowed = await eligibility.purchasable(plans, buyer)

    assert [plan.public_code for plan in allowed] == ["for-all", "for-existing"]
    assert await eligibility.purchasable([], buyer) == []
