from app.core.actor import Actor
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, ValidationError
from app.core.security.permissions import Permission, PermissionPolicy
from app.modules.users import UserDto, UserRepository


async def load_pair(
    actor: Actor, users: UserRepository, target_id: int, source_id: int
) -> tuple[UserDto, UserDto]:
    if source_id == target_id:
        raise ValidationError(
            "Cannot merge an account into itself", code=ErrorCode.MERGE_SAME_ACCOUNT
        )
    source = await users.find_by_id(source_id)
    target = await users.find_by_id(target_id)
    if source is None or target is None or source.deleted_at or target.deleted_at:
        raise NotFoundError("User not found", code=ErrorCode.USER_NOT_FOUND)
    # a staff side out of the caller's reach answers like a missing account, before
    # anything that would tell staff ids apart
    for side in (source, target):
        if side.is_privileged and not (
            PermissionPolicy.has_permission(actor, Permission.ADMINS_MANAGE)
            and (side.id == actor.id or PermissionPolicy.can_manage(actor, side))
        ):
            raise NotFoundError("User not found", code=ErrorCode.USER_NOT_FOUND)
    if source.is_privileged and target.is_privileged:
        raise ValidationError(
            "Two staff accounts can't be merged", code=ErrorCode.MERGE_BOTH_PRIVILEGED
        )
    return source, target
