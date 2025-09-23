from dishka import Provider, Scope, provide

from src.services.command import CommandService
from src.services.maintenance import MaintenanceService
from src.services.notification import NotificationService
from src.services.payment_gateway import PaymentGatewayService
from src.services.plan import PlanService
from src.services.promocode import PromocodeService
from src.services.subscription import SubscriptionService
from src.services.transaction import TransactionService
from src.services.user import UserService
from src.services.webhook import WebhookService


class ServicesProvider(Provider):
    scope = Scope.APP

    command_service = provide(source=CommandService)
    maintenance_service = provide(source=MaintenanceService)
    notification_service = provide(source=NotificationService, scope=Scope.REQUEST)
    gateway_service = provide(source=PaymentGatewayService, scope=Scope.REQUEST)
    plan_service = provide(source=PlanService, scope=Scope.REQUEST)
    promocode_service = provide(PromocodeService, scope=Scope.REQUEST)
    subscription_service = provide(SubscriptionService, scope=Scope.REQUEST)
    transaction_service = provide(TransactionService, scope=Scope.REQUEST)
    user_service = provide(source=UserService, scope=Scope.REQUEST)
    webhook_service = provide(source=WebhookService)
