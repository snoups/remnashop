from typing import cast

from dishka import Provider, Scope, provide, provide_all

from app.modules.customer_notifications.dispatch import SendCustomerTelegramDispatch
from app.modules.customer_notifications.tasks import send_customer_telegram_task
from app.modules.customer_notifications.usecases import (
    NotifyCustomerUseCase,
    SendCustomerTelegramUseCase,
)


class CustomerNotificationsProvider(Provider):
    use_cases = provide_all(NotifyCustomerUseCase, SendCustomerTelegramUseCase, scope=Scope.REQUEST)

    @provide(scope=Scope.APP)
    def send_telegram_dispatch(self) -> SendCustomerTelegramDispatch:
        return cast(SendCustomerTelegramDispatch, send_customer_telegram_task)


def get_customer_notifications_providers() -> list[Provider]:
    return [CustomerNotificationsProvider()]
