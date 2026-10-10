from app.core.actor import Actor
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.modules.users import UserDto, UserRepository, visible_user


async def get_visible_target(
    user_repository: UserRepository, actor: Actor, user_id: int
) -> UserDto:
    # a hidden staff row answers like a missing one, so ids can't be probed
    target = visible_user(actor, await user_repository.get_by_id(user_id))
    if target is None:
        raise NotFoundError(f"User '{user_id}' not found", code=ErrorCode.USER_NOT_FOUND)
    return target
