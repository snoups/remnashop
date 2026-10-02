from app.core.actor import Actor
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.blacklist.dispatch import SyncBlacklistSourcesDispatch


class SyncBlacklistSourcesUseCase(UseCase[None, None]):
    required_permission = Permission.BLACKLIST_SYNC

    def __init__(self, sync_dispatch: SyncBlacklistSourcesDispatch) -> None:
        self._sync_dispatch = sync_dispatch

    async def _execute(self, actor: Actor, data: None) -> None:
        await self._sync_dispatch.kiq()
