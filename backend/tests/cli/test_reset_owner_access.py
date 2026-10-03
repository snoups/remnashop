from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.cli.reset_owner_access import reset_owner_access
from app.core.config import AppConfig
from app.core.enums import Locale, OAuthProvider, Role
from app.core.security import verify_password
from app.core.utils.time import datetime_now
from app.modules.auth import SessionRepository
from app.modules.auth.dto import CreateSessionDto
from app.modules.oauth import CreateOAuthIdentityDto, OAuthIdentityRepository
from app.modules.passkeys import PasskeyRepository
from app.modules.passkeys.dto import CreatePasskeyCredentialDto
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


async def test_reset_owner_access_removes_planted_passkeys_and_oauth_identities(
    session: AsyncSession, config: AppConfig, user_repository: UserRepository
) -> None:
    # whoever held the owner session could have added a passkey or an OAuth
    # account, and both log in without the password
    owner = await user_repository.create(
        CreateUserDto(
            login="owner", password_hash="x:y", name="owner", role=Role.OWNER, language=Locale.EN
        )
    )
    passkeys = PasskeyRepository(session)
    identities = OAuthIdentityRepository(session)
    await passkeys.create(
        CreatePasskeyCredentialDto(
            user_id=owner.id,
            credential_id="planted",
            public_key=b"k",
            sign_count=0,
            transports=None,
            device_type="single_device",
            backed_up=False,
            name=None,
        )
    )
    await identities.create(
        CreateOAuthIdentityDto(
            user_id=owner.id,
            provider=OAuthProvider.GITHUB,
            external_id="attacker",
            external_login="attacker",
        )
    )

    assert await reset_owner_access(session, config.crypt_key.get_secret_value()) is not None

    assert await passkeys.get_by_credential_id("planted") is None
    assert await identities.list_by_user(owner.id) == []
