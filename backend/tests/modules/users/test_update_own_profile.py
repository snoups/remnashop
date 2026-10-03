import pytest

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.exceptions import ValidationError
from app.core.security import hash_password
from app.modules.users.dto import CreateUserDto, UpdateOwnProfileDto, UserDto
from app.modules.users.repository import UserRepository
from app.modules.users.usecases.update_own_profile import UpdateOwnProfileUseCase


class _NoopRevoker:
    async def revoke_all_by_user(self, user_id: int) -> None:
        return None


@pytest.fixture
async def admin(user_repository: UserRepository, uow: UnitOfWork) -> UserDto:
    async with uow:
        return await user_repository.create(CreateUserDto(name="Admin", role=Role.ADMIN))


@pytest.fixture
def use_case(
    user_repository: UserRepository, uow: UnitOfWork, config: AppConfig
) -> UpdateOwnProfileUseCase:
    return UpdateOwnProfileUseCase(user_repository, uow, config, _NoopRevoker())


async def test_update_own_profile_cleans_the_name(
    use_case: UpdateOwnProfileUseCase, admin: UserDto
) -> None:
    updated = await use_case(admin, UpdateOwnProfileDto(name="  <b>Neo</b> { $x } 😀 "))
    assert updated.name == "Neo x"


async def test_update_own_profile_rejects_a_name_with_nothing_left(
    use_case: UpdateOwnProfileUseCase, admin: UserDto
) -> None:
    with pytest.raises(ValidationError):
        await use_case(admin, UpdateOwnProfileDto(name="😀 {}"))


async def test_own_password_change_clears_password_change_required(
    use_case: UpdateOwnProfileUseCase,
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    pepper = config.crypt_key.get_secret_value()
    async with uow:
        admin = await user_repository.create(
            CreateUserDto(
                name="Temp",
                role=Role.ADMIN,
                password_hash=await hash_password("temp-password", pepper),
                password_change_required=True,
            )
        )
    assert admin.password_change_required

    updated = await use_case(
        admin,
        UpdateOwnProfileDto(current_password="temp-password", new_password="New-password-1"),
    )
    assert not updated.password_change_required
