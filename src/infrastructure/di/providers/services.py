from dishka import AnyOf, Provider, Scope, alias, provide

from src.application.common import (
    Cryptographer,
    EventPublisher,
    EventSubscriber,
    Notifier,
    Redirect,
    Remnawave,
)
from src.application.services import (
    BotService,
    CommandService,
    NotificationService,
    PricingService,
    RemnaWebhookService,
    WebhookService,
)
from src.infrastructure.services import (
    CryptographerImpl,
    EventBusImpl,
    NotificationQueue,
    RedirectImpl,
    RemnawaveImpl,
)
from src.modules.topic_notifications import TopicNotificationConfig, TopicNotificationModule


class ServicesProvider(Provider):
    scope = Scope.APP

    bot = provide(source=BotService)
    cryptographer = provide(source=CryptographerImpl, provides=Cryptographer)
    redirect = provide(source=RedirectImpl, provides=Redirect)
    pricing = provide(source=PricingService)

    event_bus = provide(EventBusImpl)
    publisher = alias(source=EventBusImpl, provides=EventPublisher)
    subscriber = alias(source=EventBusImpl, provides=EventSubscriber)

    command = provide(source=CommandService)
    webhook = provide(source=WebhookService)

    remnawave = provide(source=RemnawaveImpl, provides=Remnawave)
    remna_webhook = provide(source=RemnaWebhookService, scope=Scope.REQUEST)
    
    # подключения модуля топиков
    topic_config = provide(source=TopicNotificationConfig.get)
    topic_module = provide(source=TopicNotificationModule, scope=Scope.REQUEST)
    # подключения модуля топиков
    
    notification_queue = provide(source=NotificationQueue)
    notification = provide(
        NotificationService,
        scope=Scope.REQUEST,
        provides=AnyOf[Notifier, NotificationService],
    )
