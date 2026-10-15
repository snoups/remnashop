import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import BlacklistKind, Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.ports import EventPublisher
from app.modules.blacklist import BlacklistRepository
from app.modules.users.dto import BindTelegramDto, CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from app.modules.users.usecases import BindTelegramIdUseCase


@pytest.fixture
async def owner(user_repository: UserRepository) -> UserDto:
    return await user_repository.create(
        CreateUserDto(name="owner", login="bindowner", role=Role.OWNER)
    )


@pytest.fixture
def use_case(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> BindTelegramIdUseCase:
    return BindTelegramIdUseCase(user_repository, blacklist_repository, uow, event_publisher)


async def test_bind_sets_id_and_clears_username(use_case, user_repository, owner) -> None:
    user = await user_repository.create(CreateUserDto(name="u", telegram_id=100, username="old"))

    result = await use_case(
        owner, BindTelegramDto(user_id=user.id, telegram_id=200, client_ip="127.0.0.1")
    )

    assert result.telegram_id == 200
    assert result.username is None


async def test_bind_same_id_is_noop(use_case, user_repository, owner) -> None:
    user = await user_repository.create(CreateUserDto(name="u", telegram_id=100, username="keep"))

    result = await use_case(
        owner, BindTelegramDto(user_id=user.id, telegram_id=100, client_ip="127.0.0.1")
    )

    assert result.username == "keep"


async def test_bind_taken_id_conflicts(use_case, user_repository, owner) -> None:
    await user_repository.create(CreateUserDto(name="holder", telegram_id=300))
    user = await user_repository.create(CreateUserDto(name="u"))

    with pytest.raises(ConflictError) as error:
        await use_case(
            owner, BindTelegramDto(user_id=user.id, telegram_id=300, client_ip="127.0.0.1")
        )
    assert error.value.code == ErrorCode.TELEGRAM_ID_TAKEN


async def test_bind_blacklisted_id_rejected(
    use_case, user_repository, blacklist_repository, owner
) -> None:
    await blacklist_repository.add_entry(BlacklistKind.TELEGRAM_ID, "400")
    user = await user_repository.create(CreateUserDto(name="u"))

    with pytest.raises(ValidationError) as error:
        await use_case(
            owner, BindTelegramDto(user_id=user.id, telegram_id=400, client_ip="127.0.0.1")
        )
    assert error.value.code == ErrorCode.TELEGRAM_ID_BLACKLISTED


async def test_bind_on_staff_needs_admins_manage(use_case, user_repository) -> None:
    admin = await user_repository.create(CreateUserDto(name="a", login="binda", role=Role.ADMIN))
    actor = UserDto(
        id=admin.id,
        name="a",
        role=Role.ADMIN,
        permission_grants=["USERS_TELEGRAM_BIND"],
    )
    other_admin = await user_repository.create(
        CreateUserDto(name="b", login="bindb", role=Role.ADMIN)
    )

    with pytest.raises(NotFoundError):
        await use_case(
            actor, BindTelegramDto(user_id=other_admin.id, telegram_id=500, client_ip="127.0.0.1")
        )


async def test_bind_on_deleted_row_is_404(user_repository) -> None:
    user = await user_repository.create(CreateUserDto(name="u", telegram_id=500))
    await user_repository.anonymize(user.id)

    with pytest.raises(NotFoundError):
        await user_repository.set_telegram_id(user.id, 777)


async def test_bind_on_deleted_target_is_404(use_case, user_repository, owner) -> None:
    user = await user_repository.create(CreateUserDto(name="u"))
    await user_repository.anonymize(user.id)

    with pytest.raises(NotFoundError):
        await use_case(
            owner, BindTelegramDto(user_id=user.id, telegram_id=600, client_ip="127.0.0.1")
        )


async def test_owner_binds_telegram_on_lower_ranked_admin(use_case, user_repository, owner) -> None:
    admin = await user_repository.create(CreateUserDto(name="a", login="bindc", role=Role.ADMIN))

    result = await use_case(
        owner, BindTelegramDto(user_id=admin.id, telegram_id=700, client_ip="127.0.0.1")
    )

    assert result.telegram_id == 700
