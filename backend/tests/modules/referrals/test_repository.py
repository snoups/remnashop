from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.referral import Referral
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
    await referral_repository.create_referral(referrer_id=a, referred_id=c, level=2)

    # depth is relative to the user asked about, not the edge's stored level
    assert await referral_repository.count_by_level(referrer_id) == {1: 2, 2: 1}
    assert await referral_repository.count_by_level(a) == {1: 1}


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


async def test_list_paginated_filters_by_search_and_rewards(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
) -> None:
    root = await _create_user(user_repository, 2111)
    rewarded_child = await _create_user(user_repository, 2112)
    plain_child = await _create_user(user_repository, 2113)
    rewarded = await referral_repository.create_referral(
        referrer_id=root, referred_id=rewarded_child, level=1
    )
    plain = await referral_repository.create_referral(
        referrer_id=root, referred_id=plain_child, level=1
    )
    subscription_id = await _create_subscription(subscription_repository, rewarded_child, 2112)
    await referral_repository.create_reward(
        referral_id=rewarded.id,
        referrer_id=root,
        subscription_id=subscription_id,
        payment_key="order-search",
        type=ReferralRewardType.POINTS,
        amount=Decimal("5"),
    )

    # the referrer's telegram id matches both edges; the referred one's only its own
    _, total = await referral_repository.list_paginated(search="2111")
    assert total == 2
    items, total = await referral_repository.list_paginated(search="2113")
    assert total == 1
    assert items[0].id == plain.id

    items, _ = await referral_repository.list_paginated(has_rewards=True)
    assert [item.id for item in items] == [rewarded.id]
    items, _ = await referral_repository.list_paginated(has_rewards=False)
    assert [item.id for item in items] == [plain.id]

    items, _ = await referral_repository.list_paginated(reward_type=ReferralRewardType.POINTS)
    assert [item.id for item in items] == [rewarded.id]
    _, total = await referral_repository.list_paginated(reward_type=ReferralRewardType.EXTRA_DAYS)
    assert total == 0


async def test_summarize_counts_and_sums_filtered_referrals(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
) -> None:
    root = await _create_user(user_repository, 2121)
    child = await _create_user(user_repository, 2122)
    other_child = await _create_user(user_repository, 2123)
    grandchild = await _create_user(user_repository, 2124)
    rewarded = await referral_repository.create_referral(
        referrer_id=root, referred_id=child, level=1
    )
    await referral_repository.create_referral(referrer_id=root, referred_id=other_child, level=1)
    await referral_repository.create_referral(referrer_id=child, referred_id=grandchild, level=2)
    subscription_id = await _create_subscription(subscription_repository, child, 2122)
    for key, reward_type, amount in (
        ("order-a", ReferralRewardType.POINTS, "5"),
        ("order-b", ReferralRewardType.POINTS, "3"),
        ("order-c", ReferralRewardType.EXTRA_DAYS, "7"),
    ):
        await referral_repository.create_reward(
            referral_id=rewarded.id,
            referrer_id=root,
            subscription_id=subscription_id,
            payment_key=key,
            type=reward_type,
            amount=Decimal(amount),
        )

    summary = await referral_repository.summarize()
    assert summary.total_count == 3
    assert summary.referrers_count == 2
    assert summary.rewarded_count == 1
    assert summary.reward_amounts == {
        ReferralRewardType.POINTS: Decimal("8"),
        ReferralRewardType.EXTRA_DAYS: Decimal("7"),
    }

    summary = await referral_repository.summarize(level=2)
    assert summary.total_count == 1
    assert summary.rewarded_count == 0
    assert summary.reward_amounts == {}


async def test_summarize_created_to_is_a_snapshot(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    session: AsyncSession,
) -> None:
    root = await _create_user(user_repository, 2131)
    old_child = await _create_user(user_repository, 2132)
    new_child = await _create_user(user_repository, 2133)
    old = await referral_repository.create_referral(
        referrer_id=root, referred_id=old_child, level=1
    )
    await referral_repository.create_referral(referrer_id=root, referred_id=new_child, level=1)
    await session.execute(
        update(Referral)
        .where(Referral.id == old.id)
        .values(created_at=datetime_now() - timedelta(days=10))
    )
    # invited before the snapshot, rewarded after it
    subscription_id = await _create_subscription(subscription_repository, old_child, 2132)
    await referral_repository.create_reward(
        referral_id=old.id,
        referrer_id=root,
        subscription_id=subscription_id,
        payment_key="order-snapshot",
        type=ReferralRewardType.POINTS,
        amount=Decimal("5"),
    )

    snapshot = await referral_repository.summarize(created_to=datetime_now() - timedelta(days=1))
    assert snapshot.total_count == 1
    assert snapshot.rewarded_count == 0
    assert snapshot.reward_amounts == {}
    live = await referral_repository.summarize()
    assert live.total_count == 2
    assert live.rewarded_count == 1


async def test_downline_lists_relative_depth_and_buyer_rewards(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
) -> None:
    root = await _create_user(user_repository, 2131)
    child = await _create_user(user_repository, 2132)
    grandchild = await _create_user(user_repository, 2133)
    great = await _create_user(user_repository, 2134)
    too_deep = await _create_user(user_repository, 2135)
    root_edge = await referral_repository.create_referral(
        referrer_id=root, referred_id=child, level=1
    )
    await referral_repository.create_referral(referrer_id=child, referred_id=grandchild, level=2)
    await referral_repository.create_referral(referrer_id=grandchild, referred_id=great, level=3)
    await referral_repository.create_referral(referrer_id=great, referred_id=too_deep, level=3)

    entries, total = await referral_repository.list_downline(root)
    assert total == 3  # capped at three hops
    assert {(e.referred_id, e.parent_id, e.depth) for e in entries} == {
        (child, root, 1),
        (grandchild, child, 2),
        (great, grandchild, 3),
    }
    entries, total = await referral_repository.list_downline(root, depth=2)
    assert total == 1
    assert entries[0].referred_id == grandchild
    _, total = await referral_repository.list_downline(root, search="2134")
    assert total == 1

    subscription_id = await _create_subscription(subscription_repository, grandchild, 2133)
    await referral_repository.create_reward(
        referral_id=root_edge.id,
        referrer_id=root,
        subscription_id=subscription_id,
        payment_key="order-downline",
        type=ReferralRewardType.POINTS,
        amount=Decimal("4"),
    )
    assert await referral_repository.reward_totals_by_buyer(root, [child, grandchild]) == {
        grandchild: {ReferralRewardType.POINTS: Decimal("4")}
    }
    rewards = await referral_repository.list_rewards_by_referrer(root)
    assert [r.buyer_id for r in rewards] == [grandchild]
    assert await referral_repository.downline_depths(root, [grandchild]) == {grandchild: 2}


async def test_list_paginated_search_puts_the_users_own_edge_first(
    referral_repository: ReferralRepository, user_repository: UserRepository
) -> None:
    root = await _create_user(user_repository, 2141)
    child = await _create_user(user_repository, 2142)
    grandchild = await _create_user(user_repository, 2143)
    own = await referral_repository.create_referral(referrer_id=root, referred_id=child, level=1)
    invited = await referral_repository.create_referral(
        referrer_id=child, referred_id=grandchild, level=2
    )

    # the invite is newer, so without the search boost it would come first
    items, _ = await referral_repository.list_paginated()
    assert [item.id for item in items][:2] == [invited.id, own.id]
    items, total = await referral_repository.list_paginated(search="2142")
    assert total == 2
    assert [item.id for item in items] == [own.id, invited.id]


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


async def test_list_paginated_search_does_not_match_login(
    referral_repository: ReferralRepository, user_repository: UserRepository
) -> None:
    # the referral listing never shows a login, so searching by it would be an oracle
    referrer = await user_repository.create(
        CreateUserDto(name="r", telegram_id=2211, login="hiddenlogin")
    )
    referred = await _create_user(user_repository, 2212)
    await referral_repository.create_referral(
        referrer_id=referrer.id, referred_id=referred, level=1
    )

    _, total = await referral_repository.list_paginated(search="hiddenlogin")
    assert total == 0
    _, total = await referral_repository.list_paginated(search="2211")
    assert total == 1


async def test_create_reward_does_not_report_a_broken_reference_as_already_granted(
    referral_repository: ReferralRepository, user_repository: UserRepository
) -> None:
    referrer_id = await _create_user(user_repository, 2090)
    referred_id = await _create_user(user_repository, 2091)
    edge = await referral_repository.create_referral(
        referrer_id=referrer_id, referred_id=referred_id, level=1
    )

    # a missing subscription is not a duplicate -- the retry must see the real error
    with pytest.raises(IntegrityError):
        await referral_repository.create_reward(
            referral_id=edge.id,
            referrer_id=referrer_id,
            subscription_id=999_999,
            payment_key="order-x",
            type=ReferralRewardType.POINTS,
            amount=Decimal("1"),
        )
