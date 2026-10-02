from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import OAuthProvider
from app.core.usecase import UseCase
from app.modules.oauth.repository import OAuthIdentityRepository


class CleanupOidcIdentitiesUseCase(UseCase[None, None]):
    required_permission = None

    def __init__(self, oauth_identity_repository: OAuthIdentityRepository, uow: UnitOfWork) -> None:
        self._oauth_identity_repository = oauth_identity_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> None:
        async with self._uow:
            deleted = await self._oauth_identity_repository.delete_all_by_provider(
                OAuthProvider.OIDC
            )
        logger.info(f"OIDC issuer changed: cleared {deleted} stale oauth_identities row(s)")
