from decimal import Decimal

import pytest

from app.core.enums import ReferralAccrualStrategy, ReferralRewardType, SubscriptionStatus
from app.core.exceptions import ConflictError
from app.core.utils.time import datetime_now
from app.modules.referrals.dto import UpdateReferralSettingsDto
from app.modules.referrals.repository import ReferralRepository
from app.modules.subscriptions.dto import CreateSubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.modules.subscriptions.factories import make_plan_snapshot


async def _create_user(user_repository: UserRepository, telegram_id: int) -> int:
    user = await user_repository.create(CreateUserDto(name="u", telegram_id=telegram_id))
    return user.id


async def _create_subscription(
    subscription_repository: SubscriptionRepository, user_id: int, remnawave_user_id: int
) -> int:
    sub = await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=user_id,
            remnawave_user_id=remnawave_user_id,
            status=SubscriptionStatus.ACTIVE,
            traffic_limit=0,
            device_limit=0,
            expire_at=datetime_now(),
            url="https://example.test/sub",
            plan_snapshot=make_plan_snapshot(plan_id=1),
        )
    )
    return sub.id


async def test_get_by_referred_id_returns_none_when_unreferred(
    referral_repository: ReferralRepository, user_repository: UserRepository
) -> None:
    referred_id = await _create_user(user_repository, 2001)
    assert await referral_repository.get_by_referred_id(referred_id) is None
    assert await referral_repository.has_referrer(referred_id) is False


async def test_create_referral_then_get_by_referred_id(
    referral_repository: ReferralRepository, user_repository: UserRepository
) -> None:
    referrer_id = await _create_user(user_repository, 2002)
    referred_id = await _create_user(user_repository, 2003)

    created = await referral_repository.create_referral(
        referrer_id=referrer_id, referred_id=referred_id, level=1
    )

    found = await referral_repository.get_by_referred_id(referred_id)
    assert found is not None
    assert found.id == created.id
    assert found.referrer_id == referrer_id
    assert found.level == 1
    assert await referral_repository.has_referrer(referred_id) is True


async def test_count_by_level_groups_correctly(
    referral_repository: ReferralRepository, user_repository: UserRepository
) -> None:
    referrer_id = await _create_user(user_repository, 2004)
    a = await _create_user(user_repository, 2005)
    b = await _create_user(user_repository, 2006)
    c = await _create_user(user_repository, 2007)
    await referral_repository.create_referral(referrer_id=referrer_id, referred_id=a, level=1)
    await referral_repository.create_referral(referrer_id=referrer_id, referred_id=b, level=1)
    await referral_repository.create_referral(referrer_id=referrer_id, referred_id=c, level=2)

    counts = await referral_repository.count_by_level(referrer_id)
    assert counts == {1: 2, 2: 1}


async def test_create_reward_persists_amount(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
) -> None:
    referrer_id = await _create_user(user_repository, 2008)
    referred_id = await _create_user(user_repository, 2009)
    edge = await referral_repository.create_referral(
        referrer_id=referrer_id, referred_id=referred_id, level=1
    )
    subscription_id = await _create_subscription(subscription_repository, referred_id, 2009)

    reward = await referral_repository.create_reward(
        referral_id=edge.id,
        referrer_id=referrer_id,
        subscription_id=subscription_id,
        payment_key="order-1",
        type=ReferralRewardType.POINTS,
        amount=Decimal("12"),
    )

    assert reward.amount == Decimal("12")
    assert reward.type == ReferralRewardType.POINTS
    assert reward.subscription_id == subscription_id


async def test_create_reward_rejects_duplicate_payment_referral_pair(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
) -> None:
    referrer_id = await _create_user(user_repository, 2010)
    referred_id = await _create_user(user_repository, 2011)
    edge = await referral_repository.create_referral(
        referrer_id=referrer_id, referred_id=referred_id, level=1
    )
    subscription_id = await _create_subscription(subscription_repository, referred_id, 2011)
    await referral_repository.create_reward(
        referral_id=edge.id,
        referrer_id=referrer_id,
        subscription_id=subscription_id,
        payment_key="order-1",
        type=ReferralRewardType.POINTS,
        amount=Decimal("12"),
    )
    # another payment for the same subscription is a separate reward
    await referral_repository.create_reward(
        referral_id=edge.id,
        referrer_id=referrer_id,
        subscription_id=subscription_id,
        payment_key="order-2",
        type=ReferralRewardType.POINTS,
        amount=Decimal("12"),
    )

    with pytest.raises(ConflictError):
        await referral_repository.create_reward(
            referral_id=edge.id,
            referrer_id=referrer_id,
            subscription_id=subscription_id,
            payment_key="order-1",
            type=ReferralRewardType.POINTS,
            amount=Decimal("12"),
        )


async def test_get_settings_returns_defaults_when_no_row(
    referral_repository: ReferralRepository,
) -> None:
    settings = await referral_repository.get_settings()
    assert settings.enabled is False
    assert settings.max_level == 1
    assert settings.reward_amounts == {}


async def test_update_settings_creates_row_and_persists_reward_amounts(
    referral_repository: ReferralRepository,
) -> None:
    updated = await referral_repository.update_settings(
        UpdateReferralSettingsDto(
            enabled=True,
            max_level=3,
            accrual_strategy=ReferralAccrualStrategy.EVERY_PAYMENT,
            reward_type=ReferralRewardType.POINTS,
            reward_amounts={1: Decimal("10"), 2: Decimal("5"), 3: Decimal("2")},
        )
    )

    assert updated.enabled is True
    assert updated.max_level == 3
    assert updated.reward_amounts == {1: Decimal("10"), 2: Decimal("5"), 3: Decimal("2")}

    reread = await referral_repository.get_settings()
    assert reread.reward_amounts == {1: Decimal("10"), 2: Decimal("5"), 3: Decimal("2")}


async def test_update_settings_partial_leaves_other_fields_untouched(
    referral_repository: ReferralRepository,
) -> None:
    await referral_repository.update_settings(UpdateReferralSettingsDto(enabled=True, max_level=2))

    updated = await referral_repository.update_settings(UpdateReferralSettingsDto(max_level=3))

    assert updated.enabled is True  # untouched
    assert updated.max_level == 3


async def test_list_paginated_filters_by_level_newest_first(
    referral_repository: ReferralRepository, user_repository: UserRepository
) -> None:
    root = await _create_user(user_repository, 2101)
    child = await _create_user(user_repository, 2102)
    grandchild = await _create_user(user_repository, 2103)
    first = await referral_repository.create_referral(referrer_id=root, referred_id=child, level=1)
    second = await referral_repository.create_referral(
        referrer_id=child, referred_id=grandchild, level=2
    )

    items, total = await referral_repository.list_paginated()
    assert total == 2
    assert {item.id for item in items} == {first.id, second.id}

    items, total = await referral_repository.list_paginated(level=2)
    assert total == 1
    assert items[0].referred_id == grandchild

    items, total = await referral_repository.list_paginated(page=2, page_size=1)
    assert total == 2
    assert len(items) == 1


async def test_reward_totals_by_referral_sums_per_type(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
) -> None:
    referrer_id = await _create_user(user_repository, 2111)
    referred_id = await _create_user(user_repository, 2112)
    edge = await referral_repository.create_referral(
        referrer_id=referrer_id, referred_id=referred_id, level=1
    )
    subscription_id = await _create_subscription(subscription_repository, referred_id, 2112)
    for key, reward_type, amount in (
        ("order-a", ReferralRewardType.EXTRA_DAYS, "7"),
        ("order-b", ReferralRewardType.EXTRA_DAYS, "3"),
        ("order-c", ReferralRewardType.POINTS, "50"),
    ):
        await referral_repository.create_reward(
            referral_id=edge.id,
            referrer_id=referrer_id,
            subscription_id=subscription_id,
            payment_key=key,
            type=reward_type,
            amount=Decimal(amount),
        )

    totals = await referral_repository.reward_totals_by_referral([edge.id, edge.id + 999])

    assert set(totals) == {edge.id}
    assert totals[edge.id].count == 3
    assert totals[edge.id].amounts == {
        ReferralRewardType.EXTRA_DAYS: Decimal("10"),
        ReferralRewardType.POINTS: Decimal("50"),
    }
