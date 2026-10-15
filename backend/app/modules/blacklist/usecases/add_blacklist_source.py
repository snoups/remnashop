from __future__ import annotations

from dataclasses import replace

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.http import assert_public_https_host
from app.modules.blacklist.dto import AddBlacklistSourceDto, BlacklistSourceDto
from app.modules.blacklist.events import BlacklistSourceChangedEvent
from app.modules.blacklist.normalize import derive_source_name
from app.modules.blacklist.repository import BlacklistRepository


class AddBlacklistSourceUseCase(UseCase[AddBlacklistSourceDto, BlacklistSourceDto]):
    required_permission = Permission.BLACKLIST_SOURCE_ADD

    def __init__(
        self,
        blacklist_repository: BlacklistRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._blacklist_repository = blacklist_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: AddBlacklistSourceDto) -> BlacklistSourceDto:
        await assert_public_https_host(data.url)
        async with self._uow:
            name = (data.name or "").strip() or derive_source_name(data.url)
            source = await self._blacklist_repository.add_source(replace(data, name=name))
            await self._event_publisher.publish(
                BlacklistSourceChangedEvent(actor=actor, action="add", source_id=source.id)
            )
        return source
