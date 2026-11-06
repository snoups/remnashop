from typing import Final, Optional

from app.core.actor import Actor
from app.core.enums import Role
from app.core.exceptions import PermissionDeniedError
from app.core.security.permissions import Permission, PermissionPolicy
from app.modules.blacklist import BlacklistOriginDto, BlacklistOriginsDto
from app.modules.users.dto import BlacklistMatchOrigin

# Role.USER only, like ListUsersUseCase; reconcile never blocks staff anyway.
BLACKLIST_MATCH_ROLES: Final[tuple[Role, ...]] = (Role.USER,)


def identities_of(
    origins: BlacklistOriginsDto, origin: Optional[BlacklistMatchOrigin] = None
) -> tuple[set[int], set[str]]:
    if origin is None:
        return set(origins.telegram_ids), set(origins.emails)

    def matches(found_in: list[BlacklistOriginDto]) -> bool:
        return any((o.source_id is None) == (origin == "manual") for o in found_in)

    return (
        {value for value, found_in in origins.telegram_ids.items() if matches(found_in)},
        {value for value, found_in in origins.emails.items() if matches(found_in)},
    )


# Staff (ADMIN/OWNER) are listed by ListAdminsUseCase behind the non-grantable
# ADMINS_MANAGE. USERS_VIEW can be granted to any admin or API token, so it
# never shows staff; `include_staff` (staff can be customers too) needs
# ADMINS_MANAGE.
ALLOWED_ROLES: Final[list[Role]] = [Role.USER]
STAFF_ROLES: Final[list[Role]] = [Role.USER, Role.ADMIN, Role.OWNER]


def detail_roles(actor: Actor, user_id: Optional[int] = None) -> list[Role]:
    # one user by id: staff rows only for ADMINS_MANAGE, as in the list, or one's own
    if user_id == actor.id or PermissionPolicy.has_permission(actor, Permission.ADMINS_MANAGE):
        return STAFF_ROLES
    return ALLOWED_ROLES


def resolve_list_roles(actor: Actor, include_staff: bool) -> list[Role]:
    if not include_staff:
        return ALLOWED_ROLES
    if not PermissionPolicy.has_permission(actor, Permission.ADMINS_MANAGE):
        raise PermissionDeniedError
    return STAFF_ROLES
