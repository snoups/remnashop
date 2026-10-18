from redis.asyncio import Redis

from app.core.actor import Actor
from app.core.enums import PanelSyncDirection
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import PanelSyncStatusesDto
from app.modules.subscriptions.panel_sync import read_panel_sync_status


class GetPanelSyncStatusUseCase(UseCase[None, PanelSyncStatusesDto]):
    required_permission = Permission.SUBSCRIPTIONS_PANEL_SYNC_STATUS_VIEW

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def _execute(self, actor: Actor, data: None) -> PanelSyncStatusesDto:
        return PanelSyncStatusesDto(
            from_panel=await read_panel_sync_status(self._redis, PanelSyncDirection.FROM_PANEL),
            to_panel=await read_panel_sync_status(self._redis, PanelSyncDirection.TO_PANEL),
        )
