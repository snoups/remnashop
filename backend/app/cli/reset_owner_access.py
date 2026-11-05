from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.cli.audit import record_rescue
from app.core.enums import Role
from app.core.security import generate_password, hash_password
from app.modules.auth import SessionRepository
from app.modules.oauth import OAuthIdentityRepository
from app.modules.passkeys import PasskeyRepository
from app.modules.settings import SettingsRepository
from app.modules.users import UpdateUserDto, UserDto, UserRepository


class OwnerNotRegisteredError(Exception):
    pass


async def reset_owner_access(session: AsyncSession, pepper: str) -> Optional[tuple[UserDto, str]]:
    # Every other way in (passkeys, linked OAuth accounts, Telegram) goes too:
    # whoever held the old credentials may have planted one of their own.
    # API tokens are left alone.
    owners = await UserRepository(session).list_by_roles([Role.OWNER])
    if not owners:
        return None
    if (await SettingsRepository(session).get_oauth_settings()).owner_claim_pending:
        raise OwnerNotRegisteredError

    owner = owners[0]
    password = generate_password()
    await UserRepository(session).update_fields(
        owner.id,
        UpdateUserDto(password_hash=await hash_password(password, pepper), ip_allowlist=[]),
    )
    await SessionRepository(session).revoke_all_by_user(owner.id)
    await PasskeyRepository(session).delete_all_by_user(owner.id)
    await OAuthIdentityRepository(session).delete_all_by_user(owner.id)
    await UserRepository(session).clear_telegram_id(owner.id)
    await record_rescue(session, "reset_owner_access", owner.id)
    await session.commit()
    return owner, password
