from dishka import Provider, Scope, provide

from app.modules.payments.gateways.factory import PaymentGatewayFactory
from app.modules.payments.repository import PaymentOrderRepository
from app.modules.payments.usecases.create_checkout import CreateCheckoutUseCase
from app.modules.payments.usecases.create_test_payment import CreateTestPaymentUseCase
from app.modules.payments.usecases.get_payment_order import GetPaymentOrderUseCase
from app.modules.payments.usecases.get_payment_order_summary import (
    GetPaymentOrderSummaryUseCase,
)
from app.modules.payments.usecases.get_test_payment_status import GetTestPaymentStatusUseCase
from app.modules.payments.usecases.handle_payment_webhook import HandlePaymentWebhookUseCase
from app.modules.payments.usecases.list_payment_order_gateways import (
    ListPaymentOrderGatewaysUseCase,
)
from app.modules.payments.usecases.list_payment_orders import ListPaymentOrdersUseCase


class PaymentsProvider(Provider):
    scope = Scope.REQUEST

    payment_order_repository = provide(PaymentOrderRepository)
    create_checkout_use_case = provide(CreateCheckoutUseCase)
    create_test_payment_use_case = provide(CreateTestPaymentUseCase)
    get_test_payment_status_use_case = provide(GetTestPaymentStatusUseCase)
    list_payment_orders_use_case = provide(ListPaymentOrdersUseCase)
    list_payment_order_gateways_use_case = provide(ListPaymentOrderGatewaysUseCase)
    get_payment_order_use_case = provide(GetPaymentOrderUseCase)
    get_payment_order_summary_use_case = provide(GetPaymentOrderSummaryUseCase)
    handle_payment_webhook_use_case = provide(HandlePaymentWebhookUseCase)
    payment_gateway_factory = provide(PaymentGatewayFactory, scope=Scope.APP)


def get_payments_providers() -> list[Provider]:
    return [PaymentsProvider()]
