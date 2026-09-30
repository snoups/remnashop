from dishka import Provider, Scope, provide

from app.modules.event_log.outbox_repository import EventOutboxRepository
from app.modules.event_log.repository import EventLogRepository
from app.modules.event_log.usecases import (
    GetNotificationGroupsUseCase,
    GetNotificationsUseCase,
    ListEventLogUseCase,
    MarkNotificationsReadUseCase,
    UpdateNotificationGroupsUseCase,
)


class EventLogProvider(Provider):
    scope = Scope.REQUEST

    event_log_repository = provide(EventLogRepository)
    event_outbox_repository = provide(EventOutboxRepository)
    list_event_log_use_case = provide(ListEventLogUseCase)
    get_notifications_use_case = provide(GetNotificationsUseCase)
    mark_notifications_read_use_case = provide(MarkNotificationsReadUseCase)
    get_notification_groups_use_case = provide(GetNotificationGroupsUseCase)
    update_notification_groups_use_case = provide(UpdateNotificationGroupsUseCase)


def get_event_log_providers() -> list[Provider]:
    return [EventLogProvider()]
