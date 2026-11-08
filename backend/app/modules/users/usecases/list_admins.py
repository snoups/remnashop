from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.users.admin_sign_in import customer_sign_in_ids
from app.modules.users.dto import AdminListDto
from app.modules.users.ports import OAuthIdentityLookup
from app.modules.users.repository import UserRepository


class ListAdminsUseCase(UseCase[None, AdminListDto]):
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

    async def _execute(self, actor: Actor, data: None) -> AdminListDto:
        async with self._uow:
            admins = await self._user_repository.list_by_roles([Role.OWNER, Role.ADMIN])
            signs_in = await customer_sign_in_ids(admins, self._oauth_identity_lookup)
        return AdminListDto(admins=admins, customer_sign_in_ids=signs_in)
