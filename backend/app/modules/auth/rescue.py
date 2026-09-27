from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Role
from app.core.security import generate_password, hash_password
from app.modules.auth.repository import SessionRepository
from app.modules.users import UpdateUserDto, UserDto, UserRepository


async def reset_owner_access(session: AsyncSession, pepper: str) -> Optional[tuple[UserDto, str]]:
    # Break-glass path for app/cli: new password, empty IP allowlist, every
    # session revoked -- whoever held the old credentials is out too.
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
    await session.commit()
    return owner, password
