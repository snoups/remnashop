from datetime import timedelta
from typing import Final

from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.enums import OAuthProvider
from app.core.utils.time import datetime_now
from app.modules.auth.repository import OAuthIdentityRepository, SessionRepository
from app.worker.broker import broker

_SESSION_RETENTION_DAYS: Final[int] = 30


@broker.task(schedule=[{"cron": "45 3 * * *"}])
@inject(patch_module=True)
async def prune_stale_sessions_task(
    session_repository: FromDishka[SessionRepository],
    uow: FromDishka[UnitOfWork],
) -> None:
    async with uow:
        cutoff = datetime_now() - timedelta(days=_SESSION_RETENTION_DAYS)
        deleted = await session_repository.delete_stale(cutoff)
    logger.info(f"Pruned {deleted} expired/revoked user_sessions row(s)")


@broker.task
@inject(patch_module=True)
async def cleanup_oidc_identities_task(
    oauth_identity_repository: FromDishka[OAuthIdentityRepository],
    uow: FromDishka[UnitOfWork],
) -> None:
    async with uow:
        deleted = await oauth_identity_repository.delete_all_by_provider(OAuthProvider.OIDC)
    logger.info(f"OIDC issuer changed: cleared {deleted} stale oauth_identities row(s)")
