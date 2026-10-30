from typing import cast

from dishka import Provider, Scope, provide, provide_all

from app.modules.customer_notifications.dispatch import (
    NotifyCustomerDispatch,
    SendCustomerTelegramDispatch,
)
from app.modules.customer_notifications.repository import CustomerNotificationRepository
from app.modules.customer_notifications.tasks import (
    notify_customer_task,
    send_customer_telegram_task,
)
from app.modules.customer_notifications.usecases import (
    GetCustomerFeedUseCase,
    MarkCustomerFeedReadUseCase,
    NotifyCustomerUseCase,
    PruneCustomerNotificationsUseCase,
    SendCustomerTelegramUseCase,
    ShowPaymentCanceledUseCase,
)


class CustomerNotificationsProvider(Provider):
    customer_notification_repository = provide(CustomerNotificationRepository, scope=Scope.REQUEST)

    use_cases = provide_all(
        GetCustomerFeedUseCase,
        MarkCustomerFeedReadUseCase,
        NotifyCustomerUseCase,
        PruneCustomerNotificationsUseCase,
        SendCustomerTelegramUseCase,
        ShowPaymentCanceledUseCase,
        scope=Scope.REQUEST,
    )

    @provide(scope=Scope.APP)
    def send_telegram_dispatch(self) -> SendCustomerTelegramDispatch:
        return cast(SendCustomerTelegramDispatch, send_customer_telegram_task)

    @provide(scope=Scope.APP)
    def notify_dispatch(self) -> NotifyCustomerDispatch:
        return cast(NotifyCustomerDispatch, notify_customer_task)


def get_customer_notifications_providers() -> list[Provider]:
    return [CustomerNotificationsProvider()]
