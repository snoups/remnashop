from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Role
from app.core.security import generate_password, hash_password
from app.modules.auth.repository import SessionRepository
from app.modules.users import UpdateUserDto, UserDto, UserRepository


async def reset_owner_access(session: AsyncSession, pepper: str) -> Optional[tuple[UserDto, str]]:
    # Break-glass path for app/cli: new password, empty IP allowlist, every
    # session revoked, and every other way to sign in as the owner (passkeys,
    # linked OAuth accounts) removed -- whoever held the old credentials, or
    # planted one of their own, is out too. API tokens are left alone.
    # Lazy imports: both modules import modules.auth themselves.
    from app.modules.oauth import OAuthIdentityRepository  # noqa: PLC0415
    from app.modules.passkeys import PasskeyRepository  # noqa: PLC0415

    owners = await UserRepository(session).list_by_roles([Role.OWNER])
    if not owners:
        return None

    owner = owners[0]
    password = generate_password()
    await UserRepository(session).update_fields(
        owner.id,
        UpdateUserDto(password_hash=await hash_password(password, pepper), ip_allowlist=[]),
    )
    await SessionRepository(session).revoke_all_by_user(owner.id)
    await PasskeyRepository(session).delete_all_by_user(owner.id)
    await OAuthIdentityRepository(session).delete_all_by_user(owner.id)
    await session.commit()
    return owner, password
