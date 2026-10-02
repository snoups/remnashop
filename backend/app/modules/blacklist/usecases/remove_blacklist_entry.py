from __future__ import annotations

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.blacklist.dto import BlacklistDto, BlacklistEntryInputDto
from app.modules.blacklist.events import BlacklistEntryRemovedEvent
from app.modules.blacklist.normalize import removal_key
from app.modules.blacklist.repository import BlacklistRepository


class RemoveBlacklistEntryUseCase(UseCase[BlacklistEntryInputDto, BlacklistDto]):
    required_permission = Permission.BLACKLIST_ENTRY_REMOVE

    def __init__(
        self,
        blacklist_repository: BlacklistRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._blacklist_repository = blacklist_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: BlacklistEntryInputDto) -> BlacklistDto:
        normalized = removal_key(data.kind, data.value)
        if normalized is not None:
            async with self._uow:
                if await self._blacklist_repository.remove_entry(data.kind, data.value):
                    await self._event_publisher.publish(
                        BlacklistEntryRemovedEvent(
                            actor=actor, kind=data.kind.value, value=normalized
                        )
                    )

        async with self._uow:
            return await self._blacklist_repository.get_blacklist()
