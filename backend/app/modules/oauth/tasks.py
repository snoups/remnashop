from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.enums import OAuthProvider
from app.modules.oauth.repository import OAuthIdentityRepository
from app.worker.broker import broker


@broker.task
@inject(patch_module=True)
async def cleanup_oidc_identities_task(
    oauth_identity_repository: FromDishka[OAuthIdentityRepository],
    uow: FromDishka[UnitOfWork],
) -> None:
    async with uow:
        deleted = await oauth_identity_repository.delete_all_by_provider(OAuthProvider.OIDC)
    logger.info(f"OIDC issuer changed: cleared {deleted} stale oauth_identities row(s)")
