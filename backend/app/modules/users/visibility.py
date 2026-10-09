from typing import Optional

from app.core.actor import Actor
from app.core.security.permissions import Permission, PermissionPolicy
from app.modules.users.dto import UserDto


def visible_user(actor: Actor, user: Optional[UserDto]) -> Optional[UserDto]:
    # same rule as ListUsersUseCase: staff rows need ADMINS_MANAGE
    if user is None or not user.is_privileged or user.id == actor.id:
        return user
    return user if PermissionPolicy.has_permission(actor, Permission.ADMINS_MANAGE) else None
