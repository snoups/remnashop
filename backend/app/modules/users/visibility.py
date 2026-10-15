from typing import Optional

from app.core.actor import Actor
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.security.permissions import Permission, PermissionPolicy
from app.modules.users.dto import UserDto
from app.modules.users.repository import UserRepository


def visible_user(actor: Actor, user: Optional[UserDto]) -> Optional[UserDto]:
    # same rule as ListUsersUseCase: staff rows need ADMINS_MANAGE
    if user is None or not user.is_privileged or user.id == actor.id:
        return user
    return user if PermissionPolicy.has_permission(actor, Permission.ADMINS_MANAGE) else None


async def get_visible_target(
    user_repository: UserRepository, actor: Actor, user_id: int, *, for_update: bool = False
) -> UserDto:
    # a hidden staff row answers like a missing one, so ids can't be probed; a
    # write locks the row and skips anonymized accounts
    user = await (
        user_repository.find_live_for_update(user_id)
        if for_update
        else user_repository.find_by_id(user_id)
    )
    target = visible_user(actor, user)
    if target is None:
        raise NotFoundError(f"User '{user_id}' not found", code=ErrorCode.USER_NOT_FOUND)
    return target


def assert_manageable(actor: Actor, target: UserDto, *, allow_self: bool = False) -> None:
    # staff only from a strictly higher role; out of reach answers like missing too
    if allow_self and target.id == actor.id:
        return
    if not PermissionPolicy.can_manage(actor, target):
        raise NotFoundError(f"User '{target.id}' not found", code=ErrorCode.USER_NOT_FOUND)
