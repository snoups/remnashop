from dataclasses import dataclass
from typing import Final, Optional

from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.exceptions import PermissionDeniedError
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.modules.users.dto import DEFAULT_PAGE_SIZE, UserDto
from app.modules.users.repository import UserRepository

# Staff accounts (ADMIN/OWNER) are listed via ListAdminsUseCase, gated by the
# non-grantable ADMINS_MANAGE permission -- USERS_VIEW is grantable to a
# regular admin and to API tokens, so it must never surface admin/owner logins
# by default. `include_staff` re-opens that view (an ADMIN/OWNER can also be a
# paying customer), but only for an actor who already holds ADMINS_MANAGE --
# it must not widen what a regular USERS_VIEW grant alone can see.
ALLOWED_ROLES: Final[list[Role]] = [Role.USER]
STAFF_ROLES: Final[list[Role]] = [Role.USER, Role.ADMIN, Role.OWNER]


@dataclass(frozen=True, kw_only=True)
class ListUsersInput:
    search: Optional[str] = None
    role: Optional[Role] = None
    is_blocked: Optional[bool] = None
    include_staff: bool = False
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


class ListUsersUseCase(UseCase[ListUsersInput, tuple[list[UserDto], int]]):
    required_permission = Permission.USERS_VIEW

    def __init__(self, user_repository: UserRepository, uow: UnitOfWork) -> None:
        self._user_repository = user_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: ListUsersInput) -> tuple[list[UserDto], int]:
        async with self._uow:
            allowed_roles = ALLOWED_ROLES
            if data.include_staff:
                if not PermissionPolicy.has_permission(actor, Permission.ADMINS_MANAGE):
                    raise PermissionDeniedError
                allowed_roles = STAFF_ROLES

            roles = [data.role] if data.role in allowed_roles else allowed_roles
            return await self._user_repository.list_filtered(
                roles=roles,
                search=data.search,
                is_blocked=data.is_blocked,
                page=data.page,
                page_size=data.page_size,
            )
