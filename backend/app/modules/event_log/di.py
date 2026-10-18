from typing import cast

from dishka import Provider, Scope, provide, provide_all

from app.core.ports import OutboxEntryDispatch
from app.modules.event_log.outbox_repository import EventOutboxRepository
from app.modules.event_log.repository import EventLogRepository
from app.modules.event_log.tasks import process_outbox_entry_task
from app.modules.event_log.usecases import (
    ClearNotificationsUseCase,
    GetEventLogEntryUseCase,
    GetNotificationsUseCase,
    ListEventLogUseCase,
    MarkNotificationsReadUseCase,
    ProcessOutboxEntryUseCase,
    PruneEventLogUseCase,
    PruneOutboxUseCase,
    SweepOutboxUseCase,
)


class EventLogProvider(Provider):
    scope = Scope.REQUEST

    repositories = provide_all(
        EventLogRepository,
        EventOutboxRepository,
    )
    use_cases = provide_all(
        ListEventLogUseCase,
        GetEventLogEntryUseCase,
        GetNotificationsUseCase,
        ClearNotificationsUseCase,
        MarkNotificationsReadUseCase,
        ProcessOutboxEntryUseCase,
        SweepOutboxUseCase,
        PruneEventLogUseCase,
        PruneOutboxUseCase,
    )

    @provide(scope=Scope.APP)
    def outbox_entry_dispatch(self) -> OutboxEntryDispatch:
        return cast(OutboxEntryDispatch, process_outbox_entry_task)


def get_event_log_providers() -> list[Provider]:
    return [EventLogProvider()]
