from functools import partial

from loguru import logger

from app.core.actor import Actor, actor_user_id
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.backups.dispatch import RunBackupDispatch
from app.modules.backups.dto import (
    STALE_RUN_AFTER,
    BackupRunDto,
    CreateBackupRunDto,
    StartBackupRunDto,
)
from app.modules.backups.events import BackupChangedEvent
from app.modules.backups.repository import BackupRepository


class CreateBackupRunUseCase(UseCase[StartBackupRunDto, BackupRunDto]):
    required_permission = Permission.BACKUPS_RUN_CREATE

    def __init__(
        self,
        backup_repository: BackupRepository,
        uow: UnitOfWork,
        run_backup_dispatch: RunBackupDispatch,
        event_publisher: EventPublisher,
    ) -> None:
        self._backup_repository = backup_repository
        self._uow = uow
        self._run_backup_dispatch = run_backup_dispatch
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: StartBackupRunDto) -> BackupRunDto:
        async with self._uow:
            if await self._backup_repository.has_active(
                data.kind, started_after=datetime_now() - STALE_RUN_AFTER
            ):
                raise ConflictError(
                    f"A '{data.kind.value}' backup is already running",
                    code=ErrorCode.BACKUP_ALREADY_RUNNING,
                )

            run = await self._backup_repository.create_run(
                CreateBackupRunDto(kind=data.kind, triggered_by=actor_user_id(actor))
            )
            await self._event_publisher.publish(
                BackupChangedEvent(actor=actor, action="run", run_id=run.id, kind=data.kind)
            )
            await self._uow.after_commit(
                partial(self._run_backup_dispatch.kiq, kind=data.kind.value, run_id=run.id)
            )

        logger.info(f"{actor.log} Enqueued backup run '{run.id}' ('{data.kind.value}')")
        return run
