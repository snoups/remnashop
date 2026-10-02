from datetime import timedelta
from typing import Final

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.auth.repository import SessionRepository

_SESSION_RETENTION_DAYS: Final[int] = 30


class PruneStaleSessionsUseCase(UseCase[None, None]):
    required_permission = None

    def __init__(self, session_repository: SessionRepository, uow: UnitOfWork) -> None:
        self._session_repository = session_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> None:
        async with self._uow:
            cutoff = datetime_now() - timedelta(days=_SESSION_RETENTION_DAYS)
            deleted = await self._session_repository.delete_stale(cutoff)
        logger.info(f"Pruned {deleted} expired/revoked user_sessions row(s)")
