from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.users.admin_sign_in import customer_sign_in_ids
from app.modules.users.dto import AdminDetailDto
from app.modules.users.ports import OAuthIdentityLookup
from app.modules.users.repository import UserRepository


class GetAdminUseCase(UseCase[int, AdminDetailDto]):
    required_permission = Permission.ADMINS_MANAGE

    def __init__(
        self,
        user_repository: UserRepository,
        uow: UnitOfWork,
        oauth_identity_lookup: OAuthIdentityLookup,
    ) -> None:
        self._user_repository = user_repository
        self._uow = uow
        self._oauth_identity_lookup = oauth_identity_lookup

    async def _execute(self, actor: Actor, data: int) -> AdminDetailDto:
        async with self._uow:
            admin = await self._user_repository.find_by_id(data)
            if admin is None or admin.role not in (Role.OWNER, Role.ADMIN):
                raise NotFoundError("Admin not found", code=ErrorCode.ADMIN_NOT_FOUND)
            signs_in = await customer_sign_in_ids([admin], self._oauth_identity_lookup)
        return AdminDetailDto(admin=admin, can_sign_in_after_demote=admin.id in signs_in)
