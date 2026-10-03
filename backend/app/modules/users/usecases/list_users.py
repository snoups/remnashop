from typing import Final

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.exceptions import PermissionDeniedError
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.modules.blacklist import BlacklistRepository
from app.modules.users.dto import (
    ListUsersDto,
    UserListItemDto,
)
from app.modules.users.repository import UserRepository
from app.modules.users.usecases.list_blacklist_matches import identities_of

# Staff (ADMIN/OWNER) are listed by ListAdminsUseCase behind the non-grantable
# ADMINS_MANAGE. USERS_VIEW can be granted to any admin or API token, so it
# never shows staff; `include_staff` (staff can be customers too) needs
# ADMINS_MANAGE.
ALLOWED_ROLES: Final[list[Role]] = [Role.USER]
STAFF_ROLES: Final[list[Role]] = [Role.USER, Role.ADMIN, Role.OWNER]


def resolve_list_roles(actor: Actor, include_staff: bool) -> list[Role]:
    if not include_staff:
        return ALLOWED_ROLES
    if not PermissionPolicy.has_permission(actor, Permission.ADMINS_MANAGE):
        raise PermissionDeniedError
    return STAFF_ROLES


class ListUsersUseCase(UseCase[ListUsersDto, tuple[list[UserListItemDto], int]]):
    required_permission = Permission.USERS_VIEW

    def __init__(
        self,
        user_repository: UserRepository,
        blacklist_repository: BlacklistRepository,
        uow: UnitOfWork,
    ) -> None:
        self._user_repository = user_repository
        self._blacklist_repository = blacklist_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: ListUsersDto) -> tuple[list[UserListItemDto], int]:
        async with self._uow:
            allowed_roles = resolve_list_roles(actor, data.include_staff)
            roles = [data.role] if data.role in allowed_roles else allowed_roles
            identities = None
            if data.blocked_by is not None:
                origins = await self._blacklist_repository.identity_origins()
                identities = identities_of(origins, data.blocked_by)
            return await self._user_repository.list_filtered(
                roles=roles,
                search=data.search,
                is_blocked=True if data.blocked_by is not None else data.is_blocked,
                created_from=data.created_from,
                created_to=data.created_to,
                has_discount=data.has_discount,
                has_subscription=data.has_subscription,
                is_trial_available=data.is_trial_available,
                identities=identities,
                deleted=data.deleted,
                sort=data.sort,
                descending=data.descending,
                page=data.page,
                page_size=data.page_size,
            )
