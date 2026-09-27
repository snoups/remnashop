from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from remnapy.enums import TrafficLimitStrategy
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import AddOnGrantIdempotency, SubscriptionPurchaseIdempotency
from app.core.db.models.addon_entitlement import AddOnEntitlement
from app.core.db.models.subscription import Subscription
from app.core.db.uow import UnitOfWork
from app.core.enums import AddOnType, Currency, SubscriptionStatus
from app.core.exceptions import NotFoundError
from app.core.utils.time import datetime_now
from app.modules.subscriptions.addon_repository import AddOnRepository
from app.modules.subscriptions.dto import (
    CreateAddOnDto,
    CreateSubscriptionDto,
    UpdateSubscriptionDto,
    UpdateSubscriptionSquadsDto,
)
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.modules.subscriptions.factories import create_subscription, make_plan_snapshot

_EXPIRE_AT = datetime(2030, 1, 1, tzinfo=timezone.utc)


async def _create_user(user_repository: UserRepository, telegram_id: int) -> int:
    user = await user_repository.create(CreateUserDto(name="buyer", telegram_id=telegram_id))
    return user.id


def _create_dto(user_id: int, remnawave_user_id: int) -> CreateSubscriptionDto:
    return CreateSubscriptionDto(
        user_id=user_id,
        remnawave_user_id=remnawave_user_id,
        status=SubscriptionStatus.ACTIVE,
        traffic_limit=100,
        device_limit=3,
        expire_at=_EXPIRE_AT,
        url="https://example.com/sub/token",
        plan_snapshot=make_plan_snapshot(),
    )


async def test_create_then_list_all_returns_subscription(
    subscription_repository: SubscriptionRepository, user_repository: UserRepository
) -> None:
    user_id = await _create_user(user_repository, 111)
    created = await subscription_repository.create(_create_dto(user_id, 5001))

    subscriptions = await subscription_repository.list_all()

    assert len(subscriptions) == 1
    assert subscriptions[0].id == created.id
    assert subscriptions[0].user_id == user_id
    assert subscriptions[0].remnawave_user_id == 5001
    assert subscriptions[0].status == SubscriptionStatus.ACTIVE
    assert subscriptions[0].addon_entitlements == []


async def test_created_subscription_has_no_addon_effect_on_limits(
    subscription_repository: SubscriptionRepository, user_repository: UserRepository
) -> None:
    user_id = await _create_user(user_repository, 112)
    created = await subscription_repository.create(_create_dto(user_id, 5002))

    assert created.effective_traffic_limit == created.traffic_limit == 100
    assert created.effective_device_limit == created.device_limit == 3


async def test_update_unknown_subscription_raises_not_found(
    subscription_repository: SubscriptionRepository,
) -> None:
    with pytest.raises(NotFoundError):
        await subscription_repository.update(
            UpdateSubscriptionDto(subscription_id=999_999, tag="x")
        )


async def test_partial_update_leaves_other_fields_untouched(
    subscription_repository: SubscriptionRepository, user_repository: UserRepository
) -> None:
    user_id = await _create_user(user_repository, 113)
    created = await subscription_repository.create(_create_dto(user_id, 5003))

    updated = await subscription_repository.update(
        UpdateSubscriptionDto(subscription_id=created.id, traffic_limit=500)
    )

    assert updated.traffic_limit == 500
    assert updated.device_limit == 3  # untouched
    assert updated.tag is None  # untouched


async def test_mark_deleted_sets_deleted_status(
    subscription_repository: SubscriptionRepository, user_repository: UserRepository
) -> None:
    user_id = await _create_user(user_repository, 114)
    created = await subscription_repository.create(_create_dto(user_id, 5004))

    deleted = await subscription_repository.mark_deleted(created.id)

    assert deleted.status == SubscriptionStatus.DELETED
    # Soft delete -- the row survives for audit history, unlike PlanRepository.delete.
    subscriptions = await subscription_repository.list_all()
    assert [s.status for s in subscriptions] == [SubscriptionStatus.DELETED]


async def test_mark_deleted_unknown_subscription_raises_not_found(
    subscription_repository: SubscriptionRepository,
) -> None:
    with pytest.raises(NotFoundError):
        await subscription_repository.mark_deleted(999_999)


async def test_update_squads_replaces_assignment(
    subscription_repository: SubscriptionRepository, user_repository: UserRepository
) -> None:
    user_id = await _create_user(user_repository, 121)
    created = await subscription_repository.create(_create_dto(user_id, 5011))
    squad = uuid4()

    updated = await subscription_repository.update_squads(
        UpdateSubscriptionSquadsDto(
            subscription_id=created.id, internal_squads=[squad], external_squad=None
        )
    )

    assert updated.internal_squads == [squad]
    assert updated.external_squad is None


async def test_get_active_by_user_excludes_deleted(
    subscription_repository: SubscriptionRepository, user_repository: UserRepository
) -> None:
    user_id = await _create_user(user_repository, 122)
    active = await subscription_repository.create(_create_dto(user_id, 5012))
    to_delete = await subscription_repository.create(_create_dto(user_id, 5013))
    await subscription_repository.mark_deleted(to_delete.id)

    active_subscriptions = await subscription_repository.get_active_by_user(user_id)

    assert [s.id for s in active_subscriptions] == [active.id]


async def test_get_active_by_user_excludes_other_users(
    subscription_repository: SubscriptionRepository, user_repository: UserRepository
) -> None:
    user_a = await _create_user(user_repository, 123)
    user_b = await _create_user(user_repository, 124)
    await subscription_repository.create(_create_dto(user_a, 5014))
    await subscription_repository.create(_create_dto(user_b, 5015))

    active_for_a = await subscription_repository.get_active_by_user(user_a)

    assert len(active_for_a) == 1
    assert active_for_a[0].user_id == user_a


async def test_effective_limits_include_addon_entitlements(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    session: AsyncSession,
) -> None:
    user_id = await _create_user(user_repository, 125)
    created = await subscription_repository.create(_create_dto(user_id, 5016))

    # No GrantAddOnUseCase exists yet (that's the purchase plan) -- insert the
    # entitlement directly, same as a repository-level fixture.
    session.add(
        AddOnEntitlement(
            subscription_id=created.id,
            addon_id=None,
            type=AddOnType.TRAFFIC,
            amount=50,
            granted_at=datetime_now(),
        )
    )
    await session.flush()

    subscriptions = await subscription_repository.list_all()

    assert subscriptions[0].effective_traffic_limit == 150  # 100 base + 50 entitlement
    assert subscriptions[0].effective_device_limit == 3  # untouched, no DEVICES entitlement


async def test_get_by_id_returns_subscription(
    subscription_repository: SubscriptionRepository, user_repository: UserRepository
) -> None:
    user_id = await _create_user(user_repository, 131)
    created = await subscription_repository.create(_create_dto(user_id, 5021))

    fetched = await subscription_repository.get_by_id(created.id)

    assert fetched.id == created.id
    assert fetched.remnawave_user_id == 5021


async def test_get_by_id_unknown_subscription_raises_not_found(
    subscription_repository: SubscriptionRepository,
) -> None:
    with pytest.raises(NotFoundError):
        await subscription_repository.get_by_id(999_999)


async def test_grant_entitlement_adds_row_and_recomputes_effective_limits(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    addon_repository: AddOnRepository,
) -> None:
    user_id = await _create_user(user_repository, 133)
    created = await subscription_repository.create(_create_dto(user_id, 5023))
    # addon_entitlements.addon_id has a real FK to addons.id -- unlike the
    # None-addon_id fixture above, a non-null value here must reference a row
    # that actually exists.
    addon = await addon_repository.create(
        CreateAddOnDto(
            name="traffic-50gb-repo-test",
            type=AddOnType.TRAFFIC,
            amount=50,
            base_price=Decimal("1.99"),
        )
    )

    granted = await subscription_repository.grant_entitlement(
        subscription_id=created.id, addon_id=addon.id, addon_type=AddOnType.TRAFFIC, amount=50
    )

    assert granted.effective_traffic_limit == created.traffic_limit + 50
    assert len(granted.addon_entitlements) == 1
    assert granted.addon_entitlements[0].addon_id == addon.id


async def test_grant_entitlement_with_idempotency_key_is_not_applied_twice(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    addon_repository: AddOnRepository,
) -> None:
    user_id = await _create_user(user_repository, 5024)
    created = await subscription_repository.create(_create_dto(user_id, 5024))
    addon = await addon_repository.create(
        CreateAddOnDto(
            name="traffic-50gb-idem-test",
            type=AddOnType.TRAFFIC,
            amount=50,
            base_price=Decimal("1.99"),
        )
    )

    first = await subscription_repository.grant_entitlement(
        subscription_id=created.id,
        addon_id=addon.id,
        addon_type=AddOnType.TRAFFIC,
        amount=50,
        idempotency_key="grant-key-1",
    )
    # Drop the identity map so the second call's idempotency-key lookup issues
    # a real SELECT instead of hitting the in-session instance -- otherwise the
    # guard "passes" without proving the row reached Postgres.
    subscription_repository.session.expunge_all()
    second = await subscription_repository.grant_entitlement(
        subscription_id=created.id,
        addon_id=addon.id,
        addon_type=AddOnType.TRAFFIC,
        amount=50,
        idempotency_key="grant-key-1",
    )

    assert len(first.addon_entitlements) == 1
    assert len(second.addon_entitlements) == 1
    assert second.effective_traffic_limit == created.traffic_limit + 50


async def test_grant_entitlement_unknown_subscription_raises_not_found(
    subscription_repository: SubscriptionRepository,
) -> None:
    with pytest.raises(NotFoundError):
        await subscription_repository.grant_entitlement(
            subscription_id=999_999, addon_id=7, addon_type=AddOnType.TRAFFIC, amount=50
        )


async def test_get_by_remnawave_user_id_returns_none_for_unknown_id(
    subscription_repository: SubscriptionRepository,
) -> None:
    result = await subscription_repository.get_by_remnawave_user_id(999999)
    assert result is None


async def test_get_by_remnawave_user_id_finds_the_matching_subscription(
    subscription_repository: SubscriptionRepository, user_repository: UserRepository
) -> None:
    user_id = await _create_user(user_repository, 141)
    created = await subscription_repository.create(_create_dto(user_id, 54321))

    found = await subscription_repository.get_by_remnawave_user_id(54321)

    assert found is not None
    assert found.id == created.id


async def test_list_non_terminal_excludes_expired_and_deleted(
    subscription_repository: SubscriptionRepository, user_repository: UserRepository
) -> None:
    user_id = await _create_user(user_repository, 143)
    active = await subscription_repository.create(_create_dto(user_id, 54323))
    expired = await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=user_id,
            remnawave_user_id=54324,
            status=SubscriptionStatus.EXPIRED,
            traffic_limit=100,
            device_limit=3,
            expire_at=datetime_now() - timedelta(days=1),
            url="https://example.com/sub/expired",
            plan_snapshot=make_plan_snapshot(),
        )
    )
    deleted = await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=user_id,
            remnawave_user_id=54325,
            status=SubscriptionStatus.DELETED,
            traffic_limit=100,
            device_limit=3,
            expire_at=datetime_now() + timedelta(days=30),
            url="https://example.com/sub/deleted",
            plan_snapshot=make_plan_snapshot(),
        )
    )

    result = await subscription_repository.list_non_terminal()
    result_ids = {row.id for row in result}

    assert active.id in result_ids
    assert expired.id not in result_ids
    assert deleted.id not in result_ids


async def test_get_by_id_for_update_returns_same_shape_as_get_by_id(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    created = await create_subscription(
        subscription_repository, user_repository, telegram_id=501, remnawave_user_id=501001
    )

    async with uow:
        locked = await subscription_repository.get_by_id_for_update(created.id)

    assert locked == created


async def test_claim_idempotency_key_first_caller_wins(
    subscription_repository: SubscriptionRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        first = await subscription_repository.claim_idempotency_key("key-1")
    async with uow:
        second = await subscription_repository.claim_idempotency_key("key-1")

    assert first is True
    assert second is False


async def test_link_and_get_idempotency_key(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    created = await create_subscription(
        subscription_repository, user_repository, telegram_id=502, remnawave_user_id=502001
    )
    async with uow:
        await subscription_repository.claim_idempotency_key("key-2")
        await subscription_repository.link_idempotency_key("key-2", created.id)

    linked = await subscription_repository.get_subscription_by_idempotency_key("key-2")

    assert linked is not None
    assert linked.id == created.id


async def test_get_subscription_by_unclaimed_idempotency_key_returns_none(
    subscription_repository: SubscriptionRepository,
) -> None:
    assert await subscription_repository.get_subscription_by_idempotency_key("missing") is None


async def test_plan_snapshot_round_trips_through_create_and_get(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
) -> None:
    created = await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=503,
        remnawave_user_id=503001,
        plan_id=7,
        name="Pro",
    )

    reloaded = await subscription_repository.get_by_id(created.id)

    assert reloaded.plan_snapshot.plan_id == 7
    assert reloaded.plan_snapshot.name == "Pro"


async def test_for_update_reads_see_fresh_data_not_identity_map_stale(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    session: AsyncSession,
    uow: UnitOfWork,
) -> None:
    # Regression test for Finding 2: ensure _for_update reads use
    # populate_existing=True so they override identity-map-cached rows.
    # Setup: load a subscription via plain get_by_id (caches it in identity map).
    user = await user_repository.create(CreateUserDto(name="stale_test", telegram_id=9999))
    created = await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=user.id,
            remnawave_user_id=9999,
            status=SubscriptionStatus.ACTIVE,
            traffic_limit=100,
            device_limit=3,
            expire_at=datetime_now() + timedelta(days=30),
            url="https://example.com/sub/stale",
            plan_snapshot=make_plan_snapshot(),
        )
    )

    # Load it once to populate the session's identity map.
    cached = await subscription_repository.get_by_id(created.id)
    assert cached.status == SubscriptionStatus.ACTIVE

    # Simulate a concurrent writer updating the status directly via raw SQL
    # (outside the session).
    await session.execute(
        update(Subscription)
        .where(Subscription.id == created.id)
        .values(status=SubscriptionStatus.LIMITED)
    )
    await session.commit()

    # Now do a _for_update read in a new UoW. It should see the fresh
    # LIMITED status from the DB, not the cached ACTIVE from the identity map.
    async with uow:
        locked = await subscription_repository.get_by_id_for_update(created.id)

    assert locked.status == SubscriptionStatus.LIMITED


async def test_get_by_remnawave_user_id_ignores_deleted_rows_sharing_the_uuid(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
) -> None:
    buyer = await user_repository.create(CreateUserDto(name="dup-uuid-buyer"))
    dead = await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=buyer.id,
            remnawave_user_id=9001,
            status=SubscriptionStatus.ACTIVE,
            traffic_limit=10,
            device_limit=1,
            traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
            is_trial=True,
            internal_squads=[],
            external_squad=None,
            expire_at=datetime_now() + timedelta(days=1),
            url="https://fake-panel.test/sub/dead",
            plan_snapshot=make_plan_snapshot(is_trial=True),
        )
    )
    await subscription_repository.mark_deleted(dead.id)
    live = await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=buyer.id,
            remnawave_user_id=9001,
            status=SubscriptionStatus.ACTIVE,
            traffic_limit=100,
            device_limit=3,
            traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
            is_trial=False,
            internal_squads=[],
            external_squad=None,
            expire_at=datetime_now() + timedelta(days=30),
            url="https://fake-panel.test/sub/live",
            plan_snapshot=make_plan_snapshot(is_trial=False),
        )
    )

    found = await subscription_repository.get_by_remnawave_user_id(9001)

    assert found is not None
    assert found.id == live.id


async def test_list_paginated_excludes_deleted_by_default(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
) -> None:
    buyer = await user_repository.create(CreateUserDto(name="list-default-buyer"))
    dead = await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=buyer.id,
            remnawave_user_id=9101,
            status=SubscriptionStatus.ACTIVE,
            traffic_limit=10,
            device_limit=1,
            traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
            is_trial=False,
            internal_squads=[],
            external_squad=None,
            expire_at=datetime_now() + timedelta(days=1),
            url="https://fake-panel.test/sub/dead2",
            plan_snapshot=make_plan_snapshot(is_trial=False),
        )
    )
    await subscription_repository.mark_deleted(dead.id)

    items, total = await subscription_repository.list_paginated(status=None)
    assert dead.id not in [item.id for item in items]

    deleted_items, deleted_total = await subscription_repository.list_paginated(
        status=SubscriptionStatus.DELETED
    )
    assert dead.id in [item.id for item in deleted_items]


async def test_list_paginated_search_matches_id_and_user_id(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
) -> None:
    buyer = await user_repository.create(CreateUserDto(name="search-buyer"))
    sub = await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=buyer.id,
            remnawave_user_id=9201,
            status=SubscriptionStatus.ACTIVE,
            traffic_limit=10,
            device_limit=1,
            traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
            is_trial=False,
            internal_squads=[],
            external_squad=None,
            expire_at=datetime_now() + timedelta(days=1),
            url="https://fake-panel.test/sub/search",
            plan_snapshot=make_plan_snapshot(is_trial=False),
        )
    )

    by_user, _ = await subscription_repository.list_paginated(search=str(buyer.id))
    assert sub.id in [item.id for item in by_user]

    none, total = await subscription_repository.list_paginated(search="no-such-sub-zzz")
    assert (none, total) == ([], 0)

    huge, _ = await subscription_repository.list_paginated(search="9" * 30)
    assert huge == []


async def test_delete_stale_idempotency_keys_removes_only_old_rows(
    subscription_repository: SubscriptionRepository,
    session: AsyncSession,
) -> None:
    now = datetime.now(timezone.utc)
    old_purchase = SubscriptionPurchaseIdempotency(key="old-p", subscription_id=None)
    new_purchase = SubscriptionPurchaseIdempotency(key="new-p", subscription_id=None)
    old_addon = AddOnGrantIdempotency(key="old-a", entitlement_id=None)
    session.add_all([old_purchase, new_purchase, old_addon])
    await session.flush()
    # created_at is a server default; force the "old" rows back in time
    await session.execute(
        update(SubscriptionPurchaseIdempotency)
        .where(SubscriptionPurchaseIdempotency.key == "old-p")
        .values(created_at=now - timedelta(days=30))
    )
    await session.execute(
        update(AddOnGrantIdempotency)
        .where(AddOnGrantIdempotency.key == "old-a")
        .values(created_at=now - timedelta(days=30))
    )

    purchase_deleted, addon_deleted = await subscription_repository.delete_stale_idempotency_keys(
        now - timedelta(days=7)
    )

    assert (purchase_deleted, addon_deleted) == (1, 1)
    remaining_purchase = set(
        (await session.scalars(select(SubscriptionPurchaseIdempotency.key))).all()
    )
    assert remaining_purchase == {"new-p"}


async def test_count_active_counts_active_disabled_and_limited_but_not_expired_or_deleted(
    subscription_repository: SubscriptionRepository, user_repository: UserRepository
) -> None:
    await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=820_001,
        remnawave_user_id=820_001,
        status=SubscriptionStatus.ACTIVE,
    )
    await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=820_002,
        remnawave_user_id=820_002,
        status=SubscriptionStatus.DISABLED,
    )
    await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=820_003,
        remnawave_user_id=820_003,
        status=SubscriptionStatus.LIMITED,
    )
    await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=820_004,
        remnawave_user_id=820_004,
        status=SubscriptionStatus.EXPIRED,
    )
    await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=820_005,
        remnawave_user_id=820_005,
        status=SubscriptionStatus.DELETED,
    )

    assert await subscription_repository.count_active() == 3


async def test_count_by_status_groups_live_rows_and_excludes_deleted(
    subscription_repository: SubscriptionRepository, user_repository: UserRepository
) -> None:
    for offset, status in enumerate(
        (
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.LIMITED,
            SubscriptionStatus.EXPIRED,
            SubscriptionStatus.DELETED,
        )
    ):
        await create_subscription(
            subscription_repository,
            user_repository,
            telegram_id=821_000 + offset,
            remnawave_user_id=821_000 + offset,
            status=status,
        )

    assert await subscription_repository.count_by_status() == {
        SubscriptionStatus.ACTIVE: 2,
        SubscriptionStatus.LIMITED: 1,
        SubscriptionStatus.EXPIRED: 1,
    }


async def test_count_expiring_between_only_counts_live_rows_in_the_window(
    subscription_repository: SubscriptionRepository, user_repository: UserRepository
) -> None:
    now = datetime_now()
    await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=822_001,
        remnawave_user_id=822_001,
        status=SubscriptionStatus.ACTIVE,
        expire_at=now + timedelta(days=3),
    )
    await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=822_002,
        remnawave_user_id=822_002,
        status=SubscriptionStatus.LIMITED,
        expire_at=now + timedelta(days=6),
    )
    # outside the window
    await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=822_003,
        remnawave_user_id=822_003,
        status=SubscriptionStatus.ACTIVE,
        expire_at=now + timedelta(days=20),
    )
    # already lapsed, still ACTIVE-status
    await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=822_004,
        remnawave_user_id=822_004,
        status=SubscriptionStatus.ACTIVE,
        expire_at=now - timedelta(days=1),
    )
    # terminal status inside the window
    await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=822_005,
        remnawave_user_id=822_005,
        status=SubscriptionStatus.EXPIRED,
        expire_at=now + timedelta(days=2),
    )

    assert await subscription_repository.count_expiring_between(now, now + timedelta(days=7)) == 2


async def test_count_churn_window_counts_pre_window_subscriptions_only(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    session: AsyncSession,
) -> None:
    window_start = datetime_now() - timedelta(days=7)

    retained = await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=824_001,
        remnawave_user_id=824_001,
        status=SubscriptionStatus.ACTIVE,
        expire_at=datetime_now() + timedelta(days=60),
    )
    await session.execute(
        update(Subscription)
        .where(Subscription.id == retained.id)
        .values(created_at=window_start - timedelta(days=10))
    )
    churned = await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=824_002,
        remnawave_user_id=824_002,
        status=SubscriptionStatus.EXPIRED,
        expire_at=datetime_now() + timedelta(days=1),
    )
    await session.execute(
        update(Subscription)
        .where(Subscription.id == churned.id)
        .values(created_at=window_start - timedelta(days=10))
    )
    # created inside the window -- must be excluded from prev_active entirely
    await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=824_003,
        remnawave_user_id=824_003,
        status=SubscriptionStatus.ACTIVE,
        expire_at=datetime_now() + timedelta(days=30),
    )

    prev_active, still_active = await subscription_repository.count_churn_window(window_start)

    assert prev_active == 2
    assert still_active == 1


async def test_sum_active_mrr_by_currency_normalizes_to_30_days_and_skips_inactive(
    subscription_repository: SubscriptionRepository, user_repository: UserRepository
) -> None:
    await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=825_001,
        remnawave_user_id=825_001,
        status=SubscriptionStatus.ACTIVE,
        price_paid=Decimal("300"),
        currency=Currency.RUB,
        duration_days=30,
    )
    await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=825_002,
        remnawave_user_id=825_002,
        status=SubscriptionStatus.ACTIVE,
        price_paid=Decimal("180"),
        currency=Currency.RUB,
        duration_days=90,  # normalizes to 180 / 90 * 30 = 60
    )
    await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=825_003,
        remnawave_user_id=825_003,
        status=SubscriptionStatus.EXPIRED,
        price_paid=Decimal("999"),
        currency=Currency.RUB,
        duration_days=30,
    )

    result = await subscription_repository.sum_active_mrr_by_currency()

    assert result == {Currency.RUB: Decimal("360")}


async def test_list_user_ids_with_trial_filters_by_is_trial_and_membership(
    subscription_repository: SubscriptionRepository, user_repository: UserRepository
) -> None:
    trial_sub = await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=826_001,
        remnawave_user_id=826_001,
        status=SubscriptionStatus.ACTIVE,
        is_trial=True,
    )
    paid_sub = await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=826_002,
        remnawave_user_id=826_002,
        status=SubscriptionStatus.ACTIVE,
        is_trial=False,
    )

    result = await subscription_repository.list_user_ids_with_trial(
        [trial_sub.user_id, paid_sub.user_id]
    )

    assert result == {trial_sub.user_id}
