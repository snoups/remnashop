from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.blacklist.dto import BlacklistDto, BlacklistEntryInputDto
from app.modules.blacklist.events import BlacklistEntryAddedEvent
from app.modules.blacklist.normalize import normalize_identity
from app.modules.blacklist.repository import BlacklistRepository

if TYPE_CHECKING:
    # app.modules.users now imports BlacklistRepository (block/unblock usecases) --
    # an eager import here would cycle back into a partially-initialized
    # app.modules.users, same class of fix as core/usecase.py and core/events.py.
    pass


class AddBlacklistEntryUseCase(UseCase[BlacklistEntryInputDto, BlacklistDto]):
    required_permission = Permission.BLACKLIST_ENTRY_ADD

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
        normalized = normalize_identity(data.kind, data.value)
        if normalized is None:
            raise ValidationError(
                f"Not a valid {data.kind.value.lower()}: {data.value!r}",
                code=ErrorCode.BLACKLIST_VALUE_INVALID,
            )

        async with self._uow:
            added = await self._blacklist_repository.add_entry(data.kind, data.value)
            if added:
                await self._event_publisher.publish(
                    BlacklistEntryAddedEvent(actor=actor, kind=data.kind.value, value=normalized)
                )

        if added:
            # Deferred: app.modules.blacklist.tasks imports app.worker.broker, a
            # module-level singleton that must not load into the api/telegram
            # processes -- same reasoning as SyncBlacklistSourcesUseCase.
            from app.modules.blacklist.tasks import reconcile_blacklist_task  # noqa: PLC0415

            await reconcile_blacklist_task.kiq()  # type: ignore[call-overload]

        async with self._uow:
            return await self._blacklist_repository.get_blacklist()
