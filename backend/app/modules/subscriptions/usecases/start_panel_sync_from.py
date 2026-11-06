from redis.asyncio import Redis

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import PanelSyncDirection
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.dispatch import PanelSyncDispatch
from app.modules.subscriptions.dto import PanelSyncStatusDto, SyncFromPanelOptionsDto
from app.modules.subscriptions.panel_sync import start_panel_sync


class StartPanelSyncFromUseCase(UseCase[SyncFromPanelOptionsDto, PanelSyncStatusDto]):
    required_permission = Permission.SUBSCRIPTIONS_PANEL_SYNC_FROM

    def __init__(
        self,
        redis: Redis,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
        panel_sync_dispatch: PanelSyncDispatch,
    ) -> None:
        self._redis = redis
        self._uow = uow
        self._event_publisher = event_publisher
        self._panel_sync_dispatch = panel_sync_dispatch

    async def _execute(self, actor: Actor, data: SyncFromPanelOptionsDto) -> PanelSyncStatusDto:
        return await start_panel_sync(
            self._redis,
            self._uow,
            self._event_publisher,
            self._panel_sync_dispatch,
            actor,
            PanelSyncDirection.FROM_PANEL,
            data,
        )
