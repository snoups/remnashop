from typing import Any

from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role
from app.core.events import EventCategory
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
