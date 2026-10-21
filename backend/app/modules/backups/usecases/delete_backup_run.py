from pathlib import Path

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.backups.events import BackupChangedEvent
from app.modules.backups.repository import BackupRepository


class DeleteBackupRunUseCase(UseCase[int, None]):
    required_permission = Permission.BACKUPS_RUN_DELETE

    def __init__(
        self, backup_repository: BackupRepository, uow: UnitOfWork, event_publisher: EventPublisher
    ) -> None:
        self._backup_repository = backup_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: int) -> None:
        async with self._uow:
            run = await self._backup_repository.get_run(data)
            await self._backup_repository.delete_run(data)
            await self._event_publisher.publish(
                BackupChangedEvent(actor=actor, action="delete", run_id=data, kind=run.kind)
            )
        # unlink only after the delete commits, so a rollback keeps the file
        if run.file_path:
            Path(run.file_path).unlink(missing_ok=True)
        logger.info(f"{actor.log} Deleted backup run '{data}'")
