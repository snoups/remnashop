from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from remnapy.enums import TrafficLimitStrategy
from sqlalchemy import delete as sa_delete
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.subscription import Subscription
from app.core.db.models.user import User
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role, SubscriptionStatus
from app.core.error_codes import ErrorCode
from app.core.events import EventCategory
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.utils.time import datetime_now
from app.modules.event_log.dto import EventLogEntryDto
from app.modules.event_log.repository import EventLogRepository
from app.modules.users import repository as user_repository_module
from app.modules.users.blacklist_repository import UserBlacklistRepository
from app.modules.users.dto import CreateUserDto, UpdateUserDto, UserDto
from app.modules.users.repository import UserRepository
from app.modules.users.stats_repository import UserStatsRepository


async def _create_user(
    user_repository: UserRepository, uow: UnitOfWork, **overrides: Any
) -> UserDto:
    defaults: dict[str, Any] = {"name": "Test User", "role": Role.USER, "language": Locale.EN}
    defaults.update(overrides)

    async with uow:
        user = await user_repository.create(CreateUserDto(**defaults))
        await uow.commit()

    return user


def _add_subscription(
    session: AsyncSession, user_id: int, status: SubscriptionStatus, *, remnawave_user_id: int
) -> None:
    session.add(
        Subscription(
            user_id=user_id,
            remnawave_user_id=remnawave_user_id,
            status=status,
            traffic_limit=0,
            device_limit=0,
            traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
            internal_squads=[],
            expire_at=datetime_now() + timedelta(days=30),
            url="https://example.com/sub",
            plan_snapshot={},
        )
    )


async def test_create_and_get_by_id(user_repository: UserRepository, uow: UnitOfWork) -> None:
    created = await _create_user(user_repository, uow, telegram_id=111, name="Alice")

    fetched = await user_repository.find_by_id(created.id)

    assert fetched is not None
    assert fetched.telegram_id == 111
    assert fetched.name == "Alice"


@pytest.mark.parametrize(
    ("first", "second", "code"),
    [
        ({"login": "taken"}, {"login": "taken"}, ErrorCode.LOGIN_TAKEN),
        ({"telegram_id": 4242}, {"telegram_id": 4242}, ErrorCode.TELEGRAM_ID_TAKEN),
        ({"email": "a@example.com"}, {"email": "A@example.com"}, ErrorCode.EMAIL_TAKEN),
        ({"role": Role.OWNER}, {"role": Role.OWNER}, ErrorCode.OWNER_ALREADY_EXISTS),
    ],
)
async def test_create_maps_unique_violation_to_conflict(
    user_repository: UserRepository,
    uow: UnitOfWork,
    first: dict[str, Any],
    second: dict[str, Any],
    code: ErrorCode,
) -> None:
    await _create_user(user_repository, uow, **first)

    with pytest.raises(ConflictError) as exc_info:
        await _create_user(user_repository, uow, **second)

    assert exc_info.value.code is code


async def test_create_leaves_unmapped_violation_unmasked(
    user_repository: UserRepository, uow: UnitOfWork, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delitem(user_repository_module._UNIQUE_VIOLATIONS, "ix_users_email_canonical")
    await _create_user(user_repository, uow, email="a@example.com")

    with pytest.raises(IntegrityError):
        await _create_user(user_repository, uow, email="a@example.com")


async def test_get_by_id_missing_returns_none(user_repository: UserRepository) -> None:
    assert await user_repository.find_by_id(999_999) is None


async def test_get_by_telegram_id(user_repository: UserRepository, uow: UnitOfWork) -> None:
    await _create_user(user_repository, uow, telegram_id=222)

    assert await user_repository.find_by_telegram_id(222) is not None
    assert await user_repository.find_by_telegram_id(333) is None


async def test_get_by_email(user_repository: UserRepository, uow: UnitOfWork) -> None:
    await _create_user(user_repository, uow, email="alice@example.com")

    assert await user_repository.find_by_email("alice@example.com") is not None
    assert await user_repository.find_by_email("nobody@example.com") is None


async def test_get_by_login(user_repository: UserRepository, uow: UnitOfWork) -> None:
    await _create_user(user_repository, uow, login="admin", role=Role.OWNER)

    assert await user_repository.find_by_login("admin") is not None
    assert await user_repository.find_by_login("nobody") is None


async def test_exists_with_role(user_repository: UserRepository, uow: UnitOfWork) -> None:
    assert not await user_repository.exists_with_role(Role.OWNER)

    await _create_user(user_repository, uow, login="admin", role=Role.OWNER)

    assert await user_repository.exists_with_role(Role.OWNER)
    assert not await user_repository.exists_with_role(Role.ADMIN)


async def test_update_fields(user_repository: UserRepository, uow: UnitOfWork) -> None:
    created = await _create_user(user_repository, uow, name="Before")

    async with uow:
        updated = await user_repository.update_fields(created.id, UpdateUserDto(name="After"))
        await uow.commit()

    assert updated is not None
    assert updated.name == "After"


async def test_update_fields_sets_personal_discount(
    user_repository: UserRepository, uow: UnitOfWork
) -> None:
    created = await _create_user(user_repository, uow, name="discount-user")

    async with uow:
        updated = await user_repository.update_fields(
            created.id, UpdateUserDto(personal_discount=25)
        )
        await uow.commit()

    assert updated is not None
    assert updated.personal_discount == 25
    assert updated.purchase_discount == 0


async def test_update_fields_missing_user_returns_none(
    user_repository: UserRepository, uow: UnitOfWork
) -> None:
    async with uow:
        result = await user_repository.update_fields(999_999, UpdateUserDto(name="x"))
        await uow.commit()

    assert result is None


async def test_create_and_update_permission_and_ip_fields(
    user_repository: UserRepository, uow: UnitOfWork
) -> None:
    created = await _create_user(
        user_repository,
        uow,
        login="admin1",
        role=Role.ADMIN,
        permission_grants=["ADMINS_MANAGE"],
        permission_revokes=["OWN_ACCOUNT_MANAGE"],
        ip_allowlist=["10.0.0.1", "192.168.1.0/24"],
    )

    fetched = await user_repository.find_by_id(created.id)

    assert fetched is not None
    assert fetched.permission_grants == ["ADMINS_MANAGE"]
    assert fetched.permission_revokes == ["OWN_ACCOUNT_MANAGE"]
    assert fetched.ip_allowlist == ["10.0.0.1", "192.168.1.0/24"]


async def test_permission_and_ip_fields_default_to_none(
    user_repository: UserRepository, uow: UnitOfWork
) -> None:
    created = await _create_user(user_repository, uow)

    fetched = await user_repository.find_by_id(created.id)

    assert fetched is not None
    assert fetched.permission_grants is None
    assert fetched.permission_revokes is None
    assert fetched.ip_allowlist is None


async def test_list_by_roles(user_repository: UserRepository, uow: UnitOfWork) -> None:
    await _create_user(user_repository, uow, login="owner1", role=Role.OWNER)
    await _create_user(user_repository, uow, login="admin1", role=Role.ADMIN)
    await _create_user(user_repository, uow, name="Regular")

    privileged = await user_repository.list_by_roles([Role.OWNER, Role.ADMIN])

    assert {u.login for u in privileged} == {"owner1", "admin1"}


async def test_list_by_roles_empty_when_none_match(user_repository: UserRepository) -> None:
    assert await user_repository.list_by_roles([Role.OWNER]) == []


async def test_get_by_username(user_repository: UserRepository, uow: UnitOfWork) -> None:
    await _create_user(user_repository, uow, telegram_id=42, username="alice_tg")

    assert await user_repository.find_by_username("alice_tg") is not None
    assert await user_repository.find_by_username("nobody_tg") is None


async def test_delete_user_nulls_out_actor_id_on_their_own_event_log_entries(
    user_repository: UserRepository,
    event_log_repository: EventLogRepository,
    uow: UnitOfWork,
) -> None:
    actor = await _create_user(user_repository, uow, login="willbedeleted10", role=Role.ADMIN)

    async with uow:
        entry = await event_log_repository.create(
            EventLogEntryDto(
                category=EventCategory.ADMIN_MANAGEMENT,
                event_type="AdminCreatedEvent",
                occurred_at=datetime_now(),
                actor_id=actor.id,
                actor_login=actor.login,
                actor_name=actor.name,
            )
        )
        await uow.commit()

    # no code path hard-deletes a user any more; this pins the FK behaviour itself
    async with uow:
        await user_repository.session.execute(sa_delete(User).where(User.id == actor.id))
        await uow.commit()

    items, _ = await event_log_repository.list(page_size=200)
    persisted = next(i for i in items if i.id == entry.id)
    assert persisted.actor_id is None
    assert persisted.actor_login == "willbedeleted10"


async def test_create_assigns_a_unique_referral_code(user_repository: UserRepository) -> None:
    first = await user_repository.create(CreateUserDto(name="a", telegram_id=1))
    second = await user_repository.create(CreateUserDto(name="b", telegram_id=2))

    assert first.referral_code is not None
    assert second.referral_code is not None
    assert first.referral_code != second.referral_code


async def test_get_by_referral_code_returns_matching_user(
    user_repository: UserRepository,
) -> None:
    created = await user_repository.create(CreateUserDto(name="a", telegram_id=3))

    assert created.referral_code is not None
    found = await user_repository.find_by_referral_code(created.referral_code)

    assert found is not None
    assert found.id == created.id


async def test_get_by_referral_code_unknown_returns_none(
    user_repository: UserRepository,
) -> None:
    assert await user_repository.find_by_referral_code("NOPE0000") is None


async def test_credit_points_adds_to_existing_points(user_repository: UserRepository) -> None:
    created = await user_repository.create(CreateUserDto(name="a", telegram_id=4))

    await user_repository.credit_points(created.id, Decimal("15"))
    await user_repository.credit_points(created.id, Decimal("5"))

    updated = await user_repository.find_by_id(created.id)
    assert updated is not None
    assert updated.points == Decimal("20")


async def test_credit_points_refuses_to_overdraw(user_repository: UserRepository) -> None:
    # The floor lives in the UPDATE predicate, not in a caller's read-then-
    # write: two concurrent debits would otherwise both read the same balance
    # and both pass their own check.
    created = await user_repository.create(CreateUserDto(name="b", telegram_id=5))
    await user_repository.credit_points(created.id, Decimal("10"))

    with pytest.raises(ValidationError):
        await user_repository.credit_points(created.id, Decimal("-20"))

    unchanged = await user_repository.find_by_id(created.id)
    assert unchanged is not None
    assert unchanged.points == Decimal("10")


async def test_update_fields_sets_is_trial_available_false(
    user_repository: UserRepository, uow: UnitOfWork
) -> None:
    created = await _create_user(user_repository, uow, name="trial-user")
    assert created.is_trial_available is True

    async with uow:
        updated = await user_repository.update_fields(
            created.id, UpdateUserDto(is_trial_available=False)
        )
        await uow.commit()

    assert updated is not None
    assert updated.is_trial_available is False


async def test_list_by_ids_returns_matching_users_in_no_particular_order(
    user_repository: UserRepository,
) -> None:
    a = await user_repository.create(CreateUserDto(name="Alpha", telegram_id=910_001))
    b = await user_repository.create(CreateUserDto(name="Beta", telegram_id=910_002))
    await user_repository.create(CreateUserDto(name="Gamma", telegram_id=910_003))

    users = await user_repository.list_by_ids([a.id, b.id])

    assert {user.id for user in users} == {a.id, b.id}


async def test_list_by_ids_takes_more_ids_than_the_bind_param_cap(
    user_repository: UserRepository,
) -> None:
    a = await user_repository.create(CreateUserDto(name="Alpha", telegram_id=910_011))
    b = await user_repository.create(CreateUserDto(name="Beta", telegram_id=910_012))
    # asyncpg caps a statement at 32,767 bind parameters
    missing = [-i for i in range(1, 40_000)]

    users = await user_repository.list_by_ids([a.id, *missing, b.id])

    assert {user.id for user in users} == {a.id, b.id}


async def test_list_by_ids_empty_input_returns_empty_list(
    user_repository: UserRepository,
) -> None:
    assert await user_repository.list_by_ids([]) == []


async def test_count_total_and_new_only_counts_that_role(
    user_repository: UserRepository,
    uow: UnitOfWork,
    user_stats_repository: UserStatsRepository,
) -> None:
    await _create_user(user_repository, uow, telegram_id=810_001, role=Role.USER)
    await _create_user(user_repository, uow, telegram_id=810_002, role=Role.USER)
    await _create_user(user_repository, uow, login="admin-810", role=Role.ADMIN)

    since = datetime_now() - timedelta(days=1)
    assert (await user_stats_repository.count_total_and_new(Role.USER, since)).total == 2
    assert (await user_stats_repository.count_total_and_new(Role.ADMIN, since)).total == 1


async def test_count_total_and_new_excludes_users_created_before_cutoff(
    user_repository: UserRepository,
    uow: UnitOfWork,
    session: AsyncSession,
    user_stats_repository: UserStatsRepository,
) -> None:
    old_user = await _create_user(user_repository, uow, telegram_id=810_101, role=Role.USER)
    new_user = await _create_user(user_repository, uow, telegram_id=810_102, role=Role.USER)
    # now() is frozen for the test transaction, so both rows get the same
    # created_at; the old one is backdated by hand
    now = datetime_now()
    await session.execute(
        update(User).where(User.id == old_user.id).values(created_at=now - timedelta(days=1))
    )
    cutoff = now - timedelta(hours=1)

    assert old_user.created_at is not None
    assert new_user.created_at is not None
    counts = await user_stats_repository.count_total_and_new(Role.USER, cutoff)

    assert counts.new == 1
    assert counts.total == 2


async def test_block_matching_handles_more_ids_than_bind_param_cap(
    user_repository: UserRepository,
    uow: UnitOfWork,
    user_blacklist_repository: UserBlacklistRepository,
) -> None:
    target = await _create_user(user_repository, uow, telegram_id=40_000_001)
    telegram_ids = set(range(40_000_000, 40_040_000))

    async with uow:
        blocked = await user_blacklist_repository.block_matching(telegram_ids, set())

    assert blocked == [target.id]


async def test_list_filtered_sorts_and_filters_by_discount_and_date(
    user_repository: UserRepository, uow: UnitOfWork, session: AsyncSession
) -> None:
    low = await _create_user(user_repository, uow, name="Low")
    high = await _create_user(user_repository, uow, name="High")
    old = await _create_user(user_repository, uow, name="Old")
    async with uow:
        await user_repository.update_fields(low.id, UpdateUserDto(personal_discount=5))
        await user_repository.update_fields(high.id, UpdateUserDto(purchase_discount=30))
        await uow.commit()
    await session.execute(
        update(User).where(User.id == old.id).values(created_at=datetime_now() - timedelta(days=30))
    )

    by_discount, _ = await user_repository.list_filtered(
        roles=[Role.USER], has_discount=True, sort="discount"
    )
    assert [u.name for u in by_discount] == ["Low", "High"]

    no_discount, _ = await user_repository.list_filtered(roles=[Role.USER], has_discount=False)
    assert [u.name for u in no_discount] == ["Old"]

    recent, total = await user_repository.list_filtered(
        roles=[Role.USER], created_from=datetime_now() - timedelta(days=7)
    )
    assert {u.name for u in recent} == {"Low", "High"}
    assert total == 2


async def test_list_filtered_sorts_by_name_and_channels(
    user_repository: UserRepository, uow: UnitOfWork
) -> None:
    await _create_user(user_repository, uow, name="bob", telegram_id=1, email="b@example.com")
    await _create_user(user_repository, uow, name="Alice")
    await _create_user(user_repository, uow, name="Carol", telegram_id=2)
    # newer than Carol, so an id tiebreak alone would put it first
    await _create_user(user_repository, uow, name="Dave", login="dave")

    by_name, _ = await user_repository.list_filtered(
        roles=[Role.USER], sort="name", descending=False
    )
    assert [u.name for u in by_name] == ["Alice", "bob", "Carol", "Dave"]

    # grouped by channel type (Telegram, then email, then login), not by count
    by_channels, _ = await user_repository.list_filtered(roles=[Role.USER], sort="channels")
    assert [u.name for u in by_channels] == ["bob", "Carol", "Dave", "Alice"]


async def test_list_filtered_counts_and_sorts_by_active_subscriptions(
    user_repository: UserRepository, uow: UnitOfWork, session: AsyncSession
) -> None:
    two = await _create_user(user_repository, uow, name="Two")
    one = await _create_user(user_repository, uow, name="One")
    await _create_user(user_repository, uow, name="None")
    # created last (highest id) but registered earliest; ties go by registration date
    older = await _create_user(user_repository, uow, name="Older")
    await session.execute(
        update(User)
        .where(User.id == older.id)
        .values(created_at=datetime_now() - timedelta(days=30))
    )
    statuses = [
        (two.id, SubscriptionStatus.ACTIVE),
        (two.id, SubscriptionStatus.ACTIVE),
        (two.id, SubscriptionStatus.EXPIRED),
        (one.id, SubscriptionStatus.ACTIVE),
        (one.id, SubscriptionStatus.LIMITED),
        (one.id, SubscriptionStatus.DISABLED),
    ]
    for index, (user_id, status) in enumerate(statuses):
        _add_subscription(session, user_id, status, remnawave_user_id=900 + index)
    await session.flush()

    items, _ = await user_repository.list_filtered(roles=[Role.USER], sort="subscriptions")
    counts = [
        (u.name, u.active_subscriptions, u.limited_subscriptions, u.expired_subscriptions)
        for u in items
    ]
    assert counts == [
        ("Two", 2, 0, 1),
        ("One", 1, 1, 0),
        ("None", 0, 0, 0),
        ("Older", 0, 0, 0),
    ]


async def test_list_filtered_filters_by_subscription_trial_and_created_to(
    user_repository: UserRepository, uow: UnitOfWork, session: AsyncSession
) -> None:
    subscribed = await _create_user(user_repository, uow, name="Subscribed")
    expired = await _create_user(user_repository, uow, name="Expired")
    old = await _create_user(user_repository, uow, name="Old")
    _add_subscription(session, subscribed.id, SubscriptionStatus.ACTIVE, remnawave_user_id=701)
    _add_subscription(session, expired.id, SubscriptionStatus.EXPIRED, remnawave_user_id=702)
    await session.execute(
        update(User)
        .where(User.id == old.id)
        .values(created_at=datetime_now() - timedelta(days=30), is_trial_available=False)
    )

    with_sub, _ = await user_repository.list_filtered(roles=[Role.USER], has_subscription=True)
    assert [u.name for u in with_sub] == ["Subscribed"]

    without_sub, _ = await user_repository.list_filtered(roles=[Role.USER], has_subscription=False)
    assert {u.name for u in without_sub} == {"Expired", "Old"}

    trial_used, _ = await user_repository.list_filtered(roles=[Role.USER], is_trial_available=False)
    assert [u.name for u in trial_used] == ["Old"]

    older, total = await user_repository.list_filtered(
        roles=[Role.USER], created_to=datetime_now() - timedelta(days=7)
    )
    assert [u.name for u in older] == ["Old"]
    assert total == 1


async def test_list_stats_counts_within_roles(
    user_repository: UserRepository,
    uow: UnitOfWork,
    session: AsyncSession,
    user_stats_repository: UserStatsRepository,
) -> None:
    fresh = await _create_user(user_repository, uow, name="Fresh")
    blocked = await _create_user(user_repository, uow, name="Blocked", is_blocked=True)
    staff = await _create_user(user_repository, uow, name="Staff", login="staff1", role=Role.ADMIN)
    last_week = await _create_user(user_repository, uow, name="LastWeek")
    _add_subscription(session, fresh.id, SubscriptionStatus.EXPIRED, remnawave_user_id=801)
    _add_subscription(session, blocked.id, SubscriptionStatus.ACTIVE, remnawave_user_id=802)
    _add_subscription(session, blocked.id, SubscriptionStatus.ACTIVE, remnawave_user_id=803)
    _add_subscription(session, staff.id, SubscriptionStatus.ACTIVE, remnawave_user_id=804)
    await session.execute(
        update(User)
        .where(User.id == blocked.id)
        .values(created_at=datetime_now() - timedelta(days=40))
    )
    await session.execute(
        update(User)
        .where(User.id == last_week.id)
        .values(created_at=datetime_now() - timedelta(days=10))
    )

    now = datetime_now()
    stats = await user_stats_repository.list_stats(
        roles=[Role.USER],
        new_since=now - timedelta(days=7),
        previous_since=now - timedelta(days=14),
        growth_since=now - timedelta(days=30),
    )

    assert (stats.total, stats.new, stats.subscribed, stats.blocked) == (3, 1, 1, 1)
    assert (stats.new_previous, stats.total_growth) == (1, 2)


async def test_list_filtered_search_matches_user_id(
    user_repository: UserRepository, uow: UnitOfWork
) -> None:
    target = await _create_user(user_repository, uow, telegram_id=710_001, name="Findme")
    await _create_user(user_repository, uow, telegram_id=710_002, name="Other")

    items, _ = await user_repository.list_filtered(roles=[Role.USER], search=str(target.id))

    assert target.id in [item.id for item in items]
    assert all(item.id == target.id or item.telegram_id == target.id for item in items)


async def test_list_filtered_search_treats_like_wildcards_literally(
    user_repository: UserRepository, uow: UnitOfWork
) -> None:
    literal = await _create_user(user_repository, uow, telegram_id=710_101, name="a_c literal")
    await _create_user(user_repository, uow, telegram_id=710_102, name="abc wildcard")

    items, _ = await user_repository.list_filtered(roles=[Role.USER], search="a_c")
    assert [item.id for item in items] == [literal.id]

    items, _ = await user_repository.list_filtered(roles=[Role.USER], search="%")
    assert items == []


async def test_credit_bonus_days_adds_and_subtracts(user_repository: UserRepository) -> None:
    user = await user_repository.create(CreateUserDto(name="u", telegram_id=930_001))

    await user_repository.credit_bonus_days(user.id, 7)
    await user_repository.credit_bonus_days(user.id, -3)

    updated = await user_repository.find_by_id(user.id)
    assert updated is not None
    assert updated.bonus_days == 4


async def test_credit_bonus_days_refuses_to_go_below_zero(user_repository: UserRepository) -> None:
    user = await user_repository.create(CreateUserDto(name="u", telegram_id=930_002))
    await user_repository.credit_bonus_days(user.id, 2)

    with pytest.raises(ValidationError) as error:
        await user_repository.credit_bonus_days(user.id, -3)

    assert error.value.code is ErrorCode.BONUS_DAYS_BELOW_ZERO
    updated = await user_repository.find_by_id(user.id)
    assert updated is not None
    assert updated.bonus_days == 2


async def test_anonymize_zeroes_bonus_days(user_repository: UserRepository) -> None:
    user = await user_repository.create(CreateUserDto(name="u", telegram_id=930_003))
    await user_repository.credit_bonus_days(user.id, 5)

    anonymized = await user_repository.anonymize(user.id)

    assert anonymized is not None
    assert anonymized.bonus_days == 0


async def test_has_discount_filter_counts_the_loyalty_discount(
    user_repository: UserRepository, uow: UnitOfWork, session: AsyncSession
) -> None:
    loyal = await _create_user(user_repository, uow, name="Loyal")
    await session.execute(update(User).where(User.id == loyal.id).values(loyalty_discount=5))

    with_discount, _ = await user_repository.list_filtered(roles=[Role.USER], has_discount=True)

    assert loyal.id in {user.id for user in with_discount}


async def test_restore_purchase_discount_skips_an_order_without_a_promocode(
    user_repository: UserRepository,
) -> None:
    user = await user_repository.create(CreateUserDto(name="u", telegram_id=930_010))

    await user_repository.restore_purchase_discount(user.id, 20, None, from_promocode=True)

    restored = await user_repository.find_by_id(user.id)
    assert restored is not None
    assert restored.purchase_discount == 0


async def test_restore_purchase_discount_gives_back_an_admin_granted_one(
    user_repository: UserRepository,
) -> None:
    user = await user_repository.create(CreateUserDto(name="u", telegram_id=930_011))

    await user_repository.restore_purchase_discount(user.id, 20, None, from_promocode=False)

    restored = await user_repository.find_by_id(user.id)
    assert restored is not None
    assert (restored.purchase_discount, restored.purchase_discount_promocode_id) == (20, None)


async def test_get_many_by_ids_skips_missing(
    user_repository: UserRepository, uow: UnitOfWork
) -> None:
    first = await _create_user(user_repository, uow, name="First")
    second = await _create_user(user_repository, uow, name="Second")

    async with uow:
        found = await user_repository.get_many_by_ids([first.id, second.id, 999_999])

    assert {user.id for user in found} == {first.id, second.id}


async def test_get_for_update_returns_fresh_row(
    user_repository: UserRepository, session: AsyncSession
) -> None:
    user = await user_repository.create(CreateUserDto(name="before"))
    assert (await user_repository.find_by_id(user.id)) is not None
    await session.execute(
        update(User).where(User.id == user.id).values(name="after"),
        execution_options={"synchronize_session": False},
    )

    fresh = await user_repository.find_for_update(user.id)

    assert fresh is not None and fresh.name == "after"
    assert await user_repository.find_for_update(user.id + 100000) is None


async def test_credit_points_reports_a_missing_user(user_repository: UserRepository) -> None:
    with pytest.raises(NotFoundError) as caught:
        await user_repository.credit_points(999_999_999, Decimal("5"))

    assert caught.value.code is ErrorCode.USER_NOT_FOUND
