from dishka import Provider, Scope, provide

from app.modules.transactions.gateways.factory import PaymentGatewayFactory
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.usecases.create_checkout import CreateCheckoutUseCase
from app.modules.transactions.usecases.create_test_payment import CreateTestPaymentUseCase
from app.modules.transactions.usecases.get_test_payment_status import GetTestPaymentStatusUseCase
from app.modules.transactions.usecases.get_transaction import GetTransactionUseCase
from app.modules.transactions.usecases.get_transaction_summary import (
    GetTransactionSummaryUseCase,
)
from app.modules.transactions.usecases.handle_payment_webhook import HandlePaymentWebhookUseCase
from app.modules.transactions.usecases.list_transaction_gateways import (
    ListTransactionGatewaysUseCase,
)
from app.modules.transactions.usecases.list_transactions import ListTransactionsUseCase


class TransactionsProvider(Provider):
    scope = Scope.REQUEST

    transaction_repository = provide(TransactionRepository)
    create_checkout_use_case = provide(CreateCheckoutUseCase)
    create_test_payment_use_case = provide(CreateTestPaymentUseCase)
    get_test_payment_status_use_case = provide(GetTestPaymentStatusUseCase)
    list_transactions_use_case = provide(ListTransactionsUseCase)
    list_transaction_gateways_use_case = provide(ListTransactionGatewaysUseCase)
    get_transaction_use_case = provide(GetTransactionUseCase)
    get_transaction_summary_use_case = provide(GetTransactionSummaryUseCase)
    handle_payment_webhook_use_case = provide(HandlePaymentWebhookUseCase)
    payment_gateway_factory = provide(PaymentGatewayFactory, scope=Scope.APP)


def get_transactions_providers() -> list[Provider]:
    return [TransactionsProvider()]
