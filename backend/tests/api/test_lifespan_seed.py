from sqlalchemy.ext.asyncio import AsyncSession

from app.api.lifespan import is_first_run
from app.core.db.models import OAuthSettings
from app.core.enums import Locale, Role
from app.modules.settings import SettingsRepository
from app.modules.users import CreateUserDto, UserRepository


async def _create_owner(user_repository: UserRepository) -> None:
    await user_repository.create(
        CreateUserDto(login=None, password_hash=None, name="o", role=Role.OWNER, language=Locale.EN)
    )


async def test_first_run_without_owner(
    user_repository: UserRepository, settings_repository: SettingsRepository
) -> None:
    assert await is_first_run(user_repository, settings_repository)


async def test_not_first_run_with_owner(
    user_repository: UserRepository, settings_repository: SettingsRepository
) -> None:
    await _create_owner(user_repository)

    assert not await is_first_run(user_repository, settings_repository)


async def test_first_run_while_owner_claim_pending(
    session: AsyncSession,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
) -> None:
    await _create_owner(user_repository)
    await session.merge(OAuthSettings(id=1, owner_claim_pending=True))
    await session.flush()

    assert await is_first_run(user_repository, settings_repository)
