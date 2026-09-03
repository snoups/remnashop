import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.user import User
from app.core.enums import Locale, Role
from app.core.events import BaseEvent
from app.core.exceptions import PermissionDeniedError
from app.core.security.permissions import Permission
from app.modules.blacklist import BlacklistRepository
from app.modules.users.dto import CreateUserDto, PromoteAdminDto, UserDto
from app.modules.users.events import UsersBulkBlockedEvent, UsersBulkUnblockedEvent
from app.modules.users.repository import UserRepository
from app.modules.users.usecases.block_user import BlockUserUseCase
from app.modules.users.usecases.bulk_block_users import BulkBlockUsersUseCase
from app.modules.users.usecases.unblock_all_users import UnblockAllUsersUseCase
from app.modules.users.usecases.unblock_user import UnblockUserUseCase


@pytest.fixture
def owner() -> UserDto:
    return UserDto(id=1, telegram_id=1, name="o", role=Role.OWNER)


@pytest.fixture
def admin_actor() -> UserDto:
    # USERS_BULK_BLOCK is OWNER-only by default -- granted here per-user so this
    # actor can exercise the role guard (an ADMIN target is then a peer, not
    # subordinate, and gets skipped rather than blocked).
    return UserDto(
        id=2,
        telegram_id=2,
        name="a",
        role=Role.ADMIN,
        permission_grants=[Permission.USERS_BULK_BLOCK.value],
    )


@pytest.fixture(autouse=True)
async def _seed_actor_rows(session: AsyncSession) -> None:
    # event_outbox.actor_id is a real FK into users -- `owner`/`admin_actor`
    # above are bare DTOs, not inserted rows. Role.USER here (not the DTO's
    # own role) matches the existing test_usecases.py pattern: the role
    # check reads the in-memory actor DTO, never this row's DB column.
    for user_id, name, telegram_id in ((1, "o", 1), (2, "a", 2)):
        session.add(
            User(
                id=user_id,
                name=name,
                telegram_id=telegram_id,
                role=Role.USER,
                language=Locale.EN,
                is_blocked=False,
            )
        )
    await session.flush()


class _RecordingEventPublisher:
    def __init__(self) -> None:
        self.events: list[BaseEvent] = []

    async def publish(self, event: BaseEvent) -> None:
        self.events.append(event)


async def test_block_user_sets_flag_and_writes_cascade_entry(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    uow,
    event_publisher,
    owner,
) -> None:
    target = await user_repository.create(CreateUserDto(telegram_id=500, name="t"))

    use_case = BlockUserUseCase(user_repository, blacklist_repository, uow, event_publisher)
    result = await use_case(owner, target.id)
    assert result.is_blocked is True

    bl = await blacklist_repository.get_blacklist()
    assert 500 in bl.telegram_ids


async def test_block_user_role_guard(
    user_repository: UserRepository, blacklist_repository, uow, event_publisher
) -> None:
    # An ADMIN actor cannot block another ADMIN (equal role -> actor.role > target.role is False).
    admin_actor = UserDto(id=2, telegram_id=2, name="a", role=Role.ADMIN)
    target = await user_repository.create(CreateUserDto(telegram_id=3, name="b"))
    await user_repository.promote_to_admin(
        target.id,
        PromoteAdminDto(
            login="target-admin",
            password_hash="hash",
            permission_grants=[],
            permission_revokes=[],
        ),
    )

    use_case = BlockUserUseCase(user_repository, blacklist_repository, uow, event_publisher)
    with pytest.raises(PermissionDeniedError):
        await use_case(admin_actor, target.id)


async def test_unblock_removes_manual_cascade_entry(
    user_repository: UserRepository, blacklist_repository, uow, event_publisher, owner
) -> None:
    target = await user_repository.create(CreateUserDto(telegram_id=600, name="t"))
    await BlockUserUseCase(user_repository, blacklist_repository, uow, event_publisher)(
        owner, target.id
    )
    await UnblockUserUseCase(user_repository, blacklist_repository, uow, event_publisher)(
        owner, target.id
    )

    refetched = await user_repository.get_by_id(target.id)
    assert refetched is not None and refetched.is_blocked is False
    bl = await blacklist_repository.get_blacklist()
    assert 600 not in bl.telegram_ids


async def test_bulk_block_partitions_known_unknown_and_role_guarded(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    uow,
    admin_actor,
) -> None:
    event_publisher = _RecordingEventPublisher()
    await user_repository.create(CreateUserDto(telegram_id=800, name="blockable"))
    peer_admin = await user_repository.create(CreateUserDto(telegram_id=801, name="peer"))
    await user_repository.promote_to_admin(
        peer_admin.id,
        PromoteAdminDto(
            login="peer-admin",
            password_hash="hash",
            permission_grants=[],
            permission_revokes=[],
        ),
    )

    use_case = BulkBlockUsersUseCase(user_repository, blacklist_repository, uow, event_publisher)
    result = await use_case(admin_actor, [800, 801, 999])

    assert result.blocked == 1
    assert result.added_to_list == 1
    assert result.skipped == 1

    blocked_user = await user_repository.get_by_telegram_id(800)
    assert blocked_user is not None and blocked_user.is_blocked is True

    skipped_peer = await user_repository.get_by_telegram_id(801)
    assert skipped_peer is not None and skipped_peer.is_blocked is False

    bl = await blacklist_repository.get_blacklist()
    assert 999 in bl.telegram_ids
    assert 800 not in bl.telegram_ids

    published = [e for e in event_publisher.events if isinstance(e, UsersBulkBlockedEvent)]
    assert len(published) == 1
    assert published[0].actor == admin_actor
    assert published[0].count == 1


async def test_unblock_all_clears_flag_and_leaves_blacklist_untouched(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    uow,
    owner,
) -> None:
    event_publisher = _RecordingEventPublisher()
    first = await user_repository.create(CreateUserDto(telegram_id=900, name="first"))
    second = await user_repository.create(CreateUserDto(telegram_id=901, name="second"))
    await user_repository.set_blocked(first.id, True)
    await user_repository.set_blocked(second.id, True)

    use_case = UnblockAllUsersUseCase(user_repository, uow, event_publisher)
    count = await use_case(owner)

    assert count == 2
    refetched_first = await user_repository.get_by_id(first.id)
    refetched_second = await user_repository.get_by_id(second.id)
    assert refetched_first is not None and refetched_first.is_blocked is False
    assert refetched_second is not None and refetched_second.is_blocked is False

    bl = await blacklist_repository.get_blacklist()
    assert bl.telegram_ids == []
    assert bl.emails == []

    published = [e for e in event_publisher.events if isinstance(e, UsersBulkUnblockedEvent)]
    assert len(published) == 1
    assert published[0].actor == owner
    assert published[0].count == 2
