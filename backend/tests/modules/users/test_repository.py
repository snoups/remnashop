from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.user import User
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role
from app.core.events import EventCategory
from app.core.exceptions import ValidationError
from app.core.utils.time import datetime_now
from app.modules.event_log.dto import EventLogEntryDto
from app.modules.event_log.repository import EventLogRepository
from app.modules.users.dto import CreateUserDto, UpdateUserDto, UserDto
from app.modules.users.repository import UserRepository


async def _create_user(
    user_repository: UserRepository, uow: UnitOfWork, **overrides: Any
) -> UserDto:
    defaults: dict[str, Any] = {"name": "Test User", "role": Role.USER, "language": Locale.EN}
    defaults.update(overrides)

    async with uow:
        user = await user_repository.create(CreateUserDto(**defaults))
        await uow.commit()

    return user


async def test_create_and_get_by_id(user_repository: UserRepository, uow: UnitOfWork) -> None:
    created = await _create_user(user_repository, uow, telegram_id=111, name="Alice")

    fetched = await user_repository.get_by_id(created.id)

    assert fetched is not None
    assert fetched.telegram_id == 111
    assert fetched.name == "Alice"


async def test_get_by_id_missing_returns_none(user_repository: UserRepository) -> None:
    assert await user_repository.get_by_id(999_999) is None


async def test_get_by_telegram_id(user_repository: UserRepository, uow: UnitOfWork) -> None:
    await _create_user(user_repository, uow, telegram_id=222)

    assert await user_repository.get_by_telegram_id(222) is not None
    assert await user_repository.get_by_telegram_id(333) is None


async def test_get_by_email(user_repository: UserRepository, uow: UnitOfWork) -> None:
    await _create_user(user_repository, uow, email="alice@example.com")

    assert await user_repository.get_by_email("alice@example.com") is not None
    assert await user_repository.get_by_email("nobody@example.com") is None


async def test_get_by_login(user_repository: UserRepository, uow: UnitOfWork) -> None:
    await _create_user(user_repository, uow, login="admin", role=Role.OWNER)

    assert await user_repository.get_by_login("admin") is not None
    assert await user_repository.get_by_login("nobody") is None


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


async def test_delete(user_repository: UserRepository, uow: UnitOfWork) -> None:
    created = await _create_user(user_repository, uow)

    async with uow:
        deleted = await user_repository.delete(created.id)
        await uow.commit()

    assert deleted is True
    assert await user_repository.get_by_id(created.id) is None


async def test_delete_missing_user_returns_false(
    user_repository: UserRepository, uow: UnitOfWork
) -> None:
    async with uow:
        result = await user_repository.delete(999_999)
        await uow.commit()

    assert result is False


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

    fetched = await user_repository.get_by_id(created.id)

    assert fetched is not None
    assert fetched.permission_grants == ["ADMINS_MANAGE"]
    assert fetched.permission_revokes == ["OWN_ACCOUNT_MANAGE"]
    assert fetched.ip_allowlist == ["10.0.0.1", "192.168.1.0/24"]


async def test_permission_and_ip_fields_default_to_none(
    user_repository: UserRepository, uow: UnitOfWork
) -> None:
    created = await _create_user(user_repository, uow)

    fetched = await user_repository.get_by_id(created.id)

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

    assert await user_repository.get_by_username("alice_tg") is not None
    assert await user_repository.get_by_username("nobody_tg") is None


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

    async with uow:
        deleted = await user_repository.delete(actor.id)
        await uow.commit()

    assert deleted is True

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
    found = await user_repository.get_by_referral_code(created.referral_code)

    assert found is not None
    assert found.id == created.id


async def test_get_by_referral_code_unknown_returns_none(
    user_repository: UserRepository,
) -> None:
    assert await user_repository.get_by_referral_code("NOPE0000") is None


async def test_credit_points_adds_to_existing_points(user_repository: UserRepository) -> None:
    created = await user_repository.create(CreateUserDto(name="a", telegram_id=4))

    await user_repository.credit_points(created.id, Decimal("15.50"))
    await user_repository.credit_points(created.id, Decimal("4.50"))

    updated = await user_repository.get_by_id(created.id)
    assert updated is not None
    assert updated.points == Decimal("20.00")


async def test_credit_points_refuses_to_overdraw(user_repository: UserRepository) -> None:
    # The floor lives in the UPDATE predicate, not in a caller's read-then-
    # write: two concurrent debits would otherwise both read the same balance
    # and both pass their own check.
    created = await user_repository.create(CreateUserDto(name="b", telegram_id=5))
    await user_repository.credit_points(created.id, Decimal("10"))

    with pytest.raises(ValidationError):
        await user_repository.credit_points(created.id, Decimal("-20"))

    unchanged = await user_repository.get_by_id(created.id)
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


async def test_list_by_ids_empty_input_returns_empty_list(
    user_repository: UserRepository,
) -> None:
    assert await user_repository.list_by_ids([]) == []


async def test_count_by_role_only_counts_that_role(
    user_repository: UserRepository, uow: UnitOfWork
) -> None:
    await _create_user(user_repository, uow, telegram_id=810_001, role=Role.USER)
    await _create_user(user_repository, uow, telegram_id=810_002, role=Role.USER)
    await _create_user(user_repository, uow, login="admin-810", role=Role.ADMIN)

    assert await user_repository.count_by_role(Role.USER) == 2
    assert await user_repository.count_by_role(Role.ADMIN) == 1


async def test_count_new_since_excludes_users_created_before_cutoff(
    user_repository: UserRepository, uow: UnitOfWork, session: AsyncSession
) -> None:
    old_user = await _create_user(user_repository, uow, telegram_id=810_101, role=Role.USER)
    new_user = await _create_user(user_repository, uow, telegram_id=810_102, role=Role.USER)
    # created_at is a server default -- Postgres now() is frozen for the
    # whole test transaction, so two rows created moments apart in the same
    # test get an IDENTICAL created_at. Force the "old" row back in time
    # (same idiom as tests/modules/subscriptions/test_repository.py's
    # test_delete_stale_idempotency_keys_removes_only_old_rows) so the
    # cutoff below has something real to exclude.
    now = datetime_now()
    await session.execute(
        update(User).where(User.id == old_user.id).values(created_at=now - timedelta(days=1))
    )
    cutoff = now - timedelta(hours=1)

    assert old_user.created_at is not None
    assert new_user.created_at is not None
    count = await user_repository.count_new_since(cutoff, Role.USER)

    assert count == 1


async def test_count_registrations_by_day_groups_and_excludes_before_since(
    user_repository: UserRepository, uow: UnitOfWork
) -> None:
    since = datetime_now() - timedelta(days=1)
    await _create_user(user_repository, uow, telegram_id=810_201, role=Role.USER)
    await _create_user(user_repository, uow, telegram_id=810_202, role=Role.USER)
    await _create_user(user_repository, uow, login="admin-810-2", role=Role.ADMIN)

    rows = await user_repository.count_registrations_by_day(since, Role.USER)

    assert sum(count for _day, count in rows) == 2


async def test_list_ids_registered_since_excludes_before_since_and_other_roles(
    user_repository: UserRepository, uow: UnitOfWork, session: AsyncSession
) -> None:
    since = datetime_now() - timedelta(days=1)
    in_window = await _create_user(user_repository, uow, telegram_id=810_301, role=Role.USER)
    outside_window = await _create_user(user_repository, uow, telegram_id=810_302, role=Role.USER)
    await session.execute(
        update(User)
        .where(User.id == outside_window.id)
        .values(created_at=since - timedelta(days=1))
    )
    await _create_user(user_repository, uow, login="admin-810-3", role=Role.ADMIN)

    ids = await user_repository.list_ids_registered_since(since, Role.USER)

    assert ids == [in_window.id]


async def test_list_id_and_registration_date_since_pairs_id_with_utc_date(
    user_repository: UserRepository, uow: UnitOfWork, session: AsyncSession
) -> None:
    since = datetime_now() - timedelta(days=1)
    in_window = await _create_user(user_repository, uow, telegram_id=810_401, role=Role.USER)
    outside_window = await _create_user(user_repository, uow, telegram_id=810_402, role=Role.USER)
    await session.execute(
        update(User)
        .where(User.id == outside_window.id)
        .values(created_at=since - timedelta(days=1))
    )
    await _create_user(user_repository, uow, login="admin-810-4", role=Role.ADMIN)

    pairs = await user_repository.list_id_and_registration_date_since(since, Role.USER)

    assert len(pairs) == 1
    user_id, registered_on = pairs[0]
    assert user_id == in_window.id
    assert registered_on == datetime_now().date()
