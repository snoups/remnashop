import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.user import User
from app.core.enums import Locale, Role
from app.core.exceptions import PermissionDeniedError
from app.modules.auth.repository import SessionRepository
from app.modules.blacklist import BlacklistRepository
from app.modules.passkeys.repository import PasskeyRepository
from app.modules.users.dto import CreateUserDto, PromoteAdminDto, UserDto
from app.modules.users.repository import UserRepository
from app.modules.users.usecases.block_user import BlockUserUseCase
from app.modules.users.usecases.unblock_user import UnblockUserUseCase


@pytest.fixture
def owner() -> UserDto:
    return UserDto(id=1, telegram_id=1, name="o", role=Role.OWNER)


@pytest.fixture(autouse=True)
async def _seed_actor_rows(session: AsyncSession) -> None:
    # event_outbox.actor_id is a real FK and the actor DTOs have no rows. The
    # role check reads the in-memory DTO, so the row's role doesn't matter.
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


async def test_block_user_sets_flag_and_writes_cascade_entry(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    uow,
    event_publisher,
    owner,
    session_repository: SessionRepository,
    passkey_repository: PasskeyRepository,
) -> None:
    target = await user_repository.create(CreateUserDto(telegram_id=500, name="t"))

    use_case = BlockUserUseCase(
        user_repository,
        blacklist_repository,
        uow,
        event_publisher,
        session_repository,
        passkey_repository,
    )
    result = await use_case(owner, target.id)
    assert result.is_blocked is True

    bl = await blacklist_repository.get_blacklist()
    assert 500 in bl.telegram_ids


async def test_block_user_role_guard(
    user_repository: UserRepository,
    blacklist_repository,
    uow,
    event_publisher,
    session_repository: SessionRepository,
    passkey_repository: PasskeyRepository,
) -> None:
    # An ADMIN actor cannot block another ADMIN (equal role -> actor.role > target.role is False).
    admin_actor = UserDto(id=2, telegram_id=2, name="a", role=Role.ADMIN)
    target = await user_repository.create(CreateUserDto(telegram_id=3, name="b"))
    await user_repository.promote_to_admin(
        target.id,
        PromoteAdminDto(
            login="target-admin",
            password_hash="hash",
            password_change_required=False,
            permission_grants=[],
            permission_revokes=[],
        ),
    )

    use_case = BlockUserUseCase(
        user_repository,
        blacklist_repository,
        uow,
        event_publisher,
        session_repository,
        passkey_repository,
    )
    with pytest.raises(PermissionDeniedError):
        await use_case(admin_actor, target.id)


async def test_unblock_removes_manual_cascade_entry(
    user_repository: UserRepository,
    blacklist_repository,
    uow,
    event_publisher,
    owner,
    session_repository: SessionRepository,
    passkey_repository: PasskeyRepository,
) -> None:
    target = await user_repository.create(CreateUserDto(telegram_id=600, name="t"))
    await BlockUserUseCase(
        user_repository,
        blacklist_repository,
        uow,
        event_publisher,
        session_repository,
        passkey_repository,
    )(owner, target.id)
    await UnblockUserUseCase(user_repository, blacklist_repository, uow, event_publisher)(
        owner, target.id
    )

    refetched = await user_repository.get_by_id(target.id)
    assert refetched is not None and refetched.is_blocked is False
    bl = await blacklist_repository.get_blacklist()
    assert 600 not in bl.telegram_ids


async def test_staff_cannot_block_themselves(
    user_repository: UserRepository,
    blacklist_repository,
    uow,
    event_publisher,
    session_repository: SessionRepository,
    passkey_repository: PasskeyRepository,
) -> None:
    # equal role: the same can_manage gate that keeps an admin off another admin
    self_owner = await user_repository.create(
        CreateUserDto(login="self-owner", name="self-owner", role=Role.OWNER)
    )
    use_case = BlockUserUseCase(
        user_repository,
        blacklist_repository,
        uow,
        event_publisher,
        session_repository,
        passkey_repository,
    )

    with pytest.raises(PermissionDeniedError):
        await use_case(self_owner, self_owner.id)
