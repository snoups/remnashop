from loguru import logger
from redis.asyncio import Redis

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import BackupRunStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.backups.cancel_signal import CANCEL_SIGNAL_TTL_S, cancel_signal_key
from app.modules.backups.dto import BackupRunDto
from app.modules.backups.events import BackupChangedEvent
from app.modules.backups.repository import BackupRepository


class CancelBackupRunUseCase(UseCase[int, BackupRunDto]):
    """A queued run is canceled here; a running one is told to stop, the worker marks it."""

    required_permission = Permission.BACKUPS_RUN_CANCEL

    def __init__(
        self,
        backup_repository: BackupRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
        redis: Redis,
    ) -> None:
        self._backup_repository = backup_repository
        self._uow = uow
        self._event_publisher = event_publisher
        self._redis = redis

    async def _execute(self, actor: Actor, data: int) -> BackupRunDto:
        async with self._uow:
            run = await self._backup_repository.get_run(data)
            if run.status not in (BackupRunStatus.PENDING, BackupRunStatus.RUNNING):
                raise ValidationError(
                    "Only a queued or running backup can be canceled",
                    code=ErrorCode.BACKUP_RUN_NOT_CANCELABLE,
                )
            # false: the worker picked it up since the read above
            canceled = await self._backup_repository.cancel_if_pending(data)
            await self._event_publisher.publish(
                BackupChangedEvent(actor=actor, action="cancel", run_id=data, kind=run.kind)
            )
            run = await self._backup_repository.get_run(data)
        if not canceled:
            await self._redis.set(cancel_signal_key(data), "1", ex=CANCEL_SIGNAL_TTL_S)
        logger.info(f"{actor.log} Canceled backup run '{data}'")
        return run
