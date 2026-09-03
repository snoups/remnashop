from dishka import Provider, Scope, provide

from app.modules.event_log.outbox_repository import EventOutboxRepository
from app.modules.event_log.repository import EventLogRepository
from app.modules.event_log.usecases import ListEventLogUseCase


class EventLogProvider(Provider):
    scope = Scope.REQUEST

    event_log_repository = provide(EventLogRepository)
    event_outbox_repository = provide(EventOutboxRepository)
    list_event_log_use_case = provide(ListEventLogUseCase)


def get_event_log_providers() -> list[Provider]:
    return [EventLogProvider()]
