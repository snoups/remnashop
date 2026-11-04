import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.exceptions import NotFoundError
from app.core.ports import EventPublisher
from app.modules.users.dto import CreateUserDto, UnbindTelegramDto, UserDto
from app.modules.users.repository import UserRepository
from app.modules.users.usecases import UnbindTelegramIdUseCase


@pytest.fixture
async def owner(user_repository: UserRepository) -> UserDto:
    return await user_repository.create(
        CreateUserDto(name="owner", login="unbindowner", role=Role.OWNER)
    )


@pytest.fixture
def use_case(
    user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> UnbindTelegramIdUseCase:
    return UnbindTelegramIdUseCase(user_repository, uow, event_publisher)


async def test_unbind_clears_id_and_username(use_case, user_repository, owner) -> None:
    user = await user_repository.create(CreateUserDto(name="u", telegram_id=100, username="old"))

    result = await use_case(owner, UnbindTelegramDto(user_id=user.id, client_ip="127.0.0.1"))

    assert result.telegram_id is None
    assert result.username is None
    assert await user_repository.find_by_telegram_id(100) is None


async def test_unbind_without_id_is_noop(use_case, user_repository, owner) -> None:
    user = await user_repository.create(CreateUserDto(name="u"))

    result = await use_case(owner, UnbindTelegramDto(user_id=user.id, client_ip="127.0.0.1"))

    assert result.telegram_id is None


async def test_unbind_staff_of_equal_rank_is_out_of_reach(use_case, user_repository) -> None:
    admin = await user_repository.create(
        CreateUserDto(name="a", login="unbind-a", role=Role.ADMIN, telegram_id=500)
    )
    other = await user_repository.create(
        CreateUserDto(name="b", login="unbind-b", role=Role.ADMIN, telegram_id=501)
    )
    granted = admin.model_copy(update={"permission_grants": ["USERS_TELEGRAM_UNBIND"]})

    with pytest.raises(NotFoundError):
        await use_case(granted, UnbindTelegramDto(user_id=other.id, client_ip="127.0.0.1"))
