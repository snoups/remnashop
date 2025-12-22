from dishka import Provider, Scope, provide

from src.services.command import CommandService
from src.services.webhook import WebhookService


class ServicesProvider(Provider):
    scope = Scope.APP

    command_service = provide(source=CommandService)
    webhook_service = provide(source=WebhookService)
