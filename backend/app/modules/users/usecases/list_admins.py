from app.core.actor import Actor
from app.core.constants import CABINET_OAUTH_PROVIDERS
from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
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
            # GitHub/OIDC open only the dashboard, gone with the login
            with_oauth = await self._oauth_identity_lookup.user_ids_with_identities(
                [admin.id for admin in admins], CABINET_OAUTH_PROVIDERS
            )
        return AdminListDto(
            admins=admins,
            customer_sign_in_ids=frozenset(
                admin.id
                for admin in admins
                if admin.telegram_id is not None
                or admin.email is not None
                or admin.id in with_oauth
            ),
        )
