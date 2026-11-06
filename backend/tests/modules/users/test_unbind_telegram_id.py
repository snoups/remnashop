from typing import Optional

import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import OAuthProvider, Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError, NotFoundError
from app.core.ports import EventPublisher
from app.modules.users.dto import CreateUserDto, UnbindTelegramDto, UserDto
from app.modules.users.repository import UserRepository
from app.modules.users.usecases import UnbindTelegramIdUseCase


@pytest.fixture
async def owner(user_repository: UserRepository) -> UserDto:
    return await user_repository.create(
        CreateUserDto(name="owner", login="unbindowner", role=Role.OWNER)
    )


class _LastMethod:
    """A staff account whose Telegram is its only way into the dashboard."""

    def __init__(self) -> None:
        self.checked: list[int] = []

    async def assert_one_left(
        self,
        user: UserDto,
        *,
        without_provider: Optional[OAuthProvider] = None,
        without_passkey: bool = False,
    ) -> None:
        self.checked.append(user.id)
        if without_provider is OAuthProvider.TELEGRAM:
            raise ConflictError("No way left", code=ErrorCode.LAST_SIGN_IN_METHOD)


@pytest.fixture
def check() -> _LastMethod:
    return _LastMethod()


@pytest.fixture
def use_case(
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    check: _LastMethod,
) -> UnbindTelegramIdUseCase:
    return UnbindTelegramIdUseCase(user_repository, uow, event_publisher, check)


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


async def test_unbind_keeps_a_staff_accounts_last_sign_in_method(
    use_case, user_repository, uow, owner, check
) -> None:
    async with uow:
        admin = await user_repository.create(
            CreateUserDto(name="a", login="unbind-last", role=Role.ADMIN, telegram_id=502)
        )
        # a refused call rolls back, the account must outlive it
        await uow.commit()

    with pytest.raises(ConflictError) as error:
        await use_case(owner, UnbindTelegramDto(user_id=admin.id, client_ip="127.0.0.1"))

    assert error.value.code is ErrorCode.LAST_SIGN_IN_METHOD
    assert check.checked == [admin.id]
    kept = await user_repository.find_by_id(admin.id)
    assert kept is not None and kept.telegram_id == 502


async def test_unbind_does_not_check_a_customers_sign_in(
    use_case, user_repository, owner, check
) -> None:
    user = await user_repository.create(CreateUserDto(name="u", telegram_id=503))

    await use_case(owner, UnbindTelegramDto(user_id=user.id, client_ip="127.0.0.1"))

    assert check.checked == []
