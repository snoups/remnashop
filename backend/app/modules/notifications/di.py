from dishka import Provider, Scope, provide, provide_all

from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.sources import BotTokenSource, NotificationRendererFactory
from app.modules.notifications.usecases import (
    DeletePushSubscriptionUseCase,
    DeliverNotificationUseCase,
    GenerateVapidKeysUseCase,
    GetNotificationChannelsUseCase,
    GetNotificationSettingsUseCase,
    GetPushPublicKeyUseCase,
    ListPushSubscriptionsUseCase,
    SendTelegramTextsUseCase,
    SendTestPushUseCase,
    SubscribePushUseCase,
    UpdateNotificationChannelsUseCase,
    UpdateNotificationSettingsUseCase,
)
from app.modules.notifications.webpush import WebPushSender


class NotificationsProvider(Provider):
    scope = Scope.REQUEST

    notification_repository = provide(NotificationRepository)
    web_push_sender = provide(WebPushSender)
    bot_token_source = provide(BotTokenSource)
    renderer_factory = provide(NotificationRendererFactory)
    use_cases = provide_all(
        GetNotificationChannelsUseCase,
        UpdateNotificationChannelsUseCase,
        GetNotificationSettingsUseCase,
        UpdateNotificationSettingsUseCase,
        GenerateVapidKeysUseCase,
        GetPushPublicKeyUseCase,
        ListPushSubscriptionsUseCase,
        SubscribePushUseCase,
        DeletePushSubscriptionUseCase,
        SendTestPushUseCase,
        DeliverNotificationUseCase,
        SendTelegramTextsUseCase,
    )


def get_notifications_providers() -> list[Provider]:
    return [NotificationsProvider()]
