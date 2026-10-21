from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.blacklist.dispatch import ReconcileBlacklistDispatch
from app.modules.blacklist.dto import BlacklistDto, BlacklistEntryInputDto
from app.modules.blacklist.events import BlacklistEntryAddedEvent
from app.modules.blacklist.normalize import normalize_identity
from app.modules.blacklist.repository import BlacklistRepository


class AddBlacklistEntryUseCase(UseCase[BlacklistEntryInputDto, BlacklistDto]):
    required_permission = Permission.BLACKLIST_ENTRY_ADD

    def __init__(
        self,
        blacklist_repository: BlacklistRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
        reconcile_dispatch: ReconcileBlacklistDispatch,
    ) -> None:
        self._blacklist_repository = blacklist_repository
        self._uow = uow
        self._event_publisher = event_publisher
        self._reconcile_dispatch = reconcile_dispatch

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
                    BlacklistEntryAddedEvent(actor=actor, kind=data.kind, value=normalized)
                )
                await self._uow.after_commit(self._reconcile_dispatch.kiq)

        async with self._uow:
            return await self._blacklist_repository.get_blacklist()
