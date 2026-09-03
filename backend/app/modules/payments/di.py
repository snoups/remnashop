from dishka import Provider, Scope, provide

from app.modules.payments.gateways.factory import PaymentGatewayFactory
from app.modules.payments.repository import PaymentOrderRepository
from app.modules.payments.usecases.create_checkout import CreateCheckoutUseCase
from app.modules.payments.usecases.get_payment_order import GetPaymentOrderUseCase
from app.modules.payments.usecases.handle_payment_webhook import HandlePaymentWebhookUseCase
from app.modules.payments.usecases.list_payment_orders import ListPaymentOrdersUseCase


class PaymentsProvider(Provider):
    scope = Scope.REQUEST

    payment_order_repository = provide(PaymentOrderRepository)
    create_checkout_use_case = provide(CreateCheckoutUseCase)
    list_payment_orders_use_case = provide(ListPaymentOrdersUseCase)
    get_payment_order_use_case = provide(GetPaymentOrderUseCase)
    handle_payment_webhook_use_case = provide(HandlePaymentWebhookUseCase)
    payment_gateway_factory = provide(PaymentGatewayFactory, scope=Scope.APP)


def get_payments_providers() -> list[Provider]:
    return [PaymentsProvider()]
