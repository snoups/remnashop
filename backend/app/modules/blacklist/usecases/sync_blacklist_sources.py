from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.blacklist.dispatch import SyncBlacklistSourcesDispatch
from app.modules.blacklist.events import BlacklistSourceChangedEvent


class SyncBlacklistSourcesUseCase(UseCase[None, None]):
    required_permission = Permission.BLACKLIST_SYNC

    def __init__(
        self,
        sync_dispatch: SyncBlacklistSourcesDispatch,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._sync_dispatch = sync_dispatch
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: None) -> None:
        async with self._uow:
            await self._event_publisher.publish(
                BlacklistSourceChangedEvent(actor=actor, action="sync")
            )
            await self._uow.after_commit(self._sync_dispatch.kiq)
