from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.enums import Locale, Role
from app.core.security import verify_password
from app.core.utils.time import datetime_now
from app.modules.auth import SessionRepository, reset_owner_access
from app.modules.auth.dto import CreateSessionDto
from app.modules.users import CreateUserDto, UpdateUserDto, UserRepository


async def test_reset_owner_access_without_owner_returns_none(
    session: AsyncSession, config: AppConfig
) -> None:
    assert await reset_owner_access(session, config.crypt_key.get_secret_value()) is None


async def test_reset_owner_access_resets_password_allowlist_and_sessions(
    session: AsyncSession,
    config: AppConfig,
    user_repository: UserRepository,
    session_repository: SessionRepository,
) -> None:
    pepper = config.crypt_key.get_secret_value()
    owner = await user_repository.create(
        CreateUserDto(
            login="owner", password_hash="x:y", name="owner", role=Role.OWNER, language=Locale.EN
        )
    )
    await user_repository.update_fields(owner.id, UpdateUserDto(ip_allowlist=["10.0.0.1"]))
    await session_repository.create(
        CreateSessionDto(
            user_id=owner.id,
            refresh_token_hash="h",
            ip_address="10.0.0.1",
            user_agent=None,
            expires_at=datetime_now() + timedelta(days=1),
        )
    )

    result = await reset_owner_access(session, pepper)

    assert result is not None
    reset, password = result
    assert reset.id == owner.id
    updated = await user_repository.get_by_id(owner.id)
    assert updated is not None
    assert updated.ip_allowlist == []
    assert updated.password_hash and await verify_password(password, updated.password_hash, pepper)
    assert await session_repository.list_active_by_user(owner.id) == []
