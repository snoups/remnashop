from datetime import timedelta
from typing import Final

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.broadcasts.dispatch import (
    DeliverBroadcastDispatch,
    DeliverBroadcastEmailDispatch,
    StartBroadcastDispatch,
)
from app.modules.broadcasts.repository import BroadcastRepository

STALL_AFTER: Final[timedelta] = timedelta(minutes=5)


class TickBroadcastsUseCase(UseCase[None, None]):
    required_permission = None

    def __init__(
        self,
        broadcast_repository: BroadcastRepository,
        start_dispatch: StartBroadcastDispatch,
        deliver_dispatch: DeliverBroadcastDispatch,
        email_dispatch: DeliverBroadcastEmailDispatch,
        uow: UnitOfWork,
    ) -> None:
        self._broadcast_repository = broadcast_repository
        self._start_dispatch = start_dispatch
        self._deliver_dispatch = deliver_dispatch
        self._email_dispatch = email_dispatch
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> None:
        now = datetime_now()
        async with self._uow:
            stalled = await self._broadcast_repository.list_stalled(now - STALL_AFTER)
            due = (
                None
                if await self._broadcast_repository.has_sending()
                else await self._broadcast_repository.next_due(now)
            )
        for broadcast_id in stalled:
            # each chain no-ops while its own lock is held or it has nothing left
            await self._deliver_dispatch.kiq(broadcast_id=broadcast_id)
            await self._email_dispatch.kiq(broadcast_id=broadcast_id)
        if due is not None:
            await self._start_dispatch.kiq(broadcast_id=due)
