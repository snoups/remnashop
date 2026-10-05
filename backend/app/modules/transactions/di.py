from collections.abc import AsyncIterator

import httpx
from dishka import Provider, Scope, alias, provide, provide_all

from app.core.ports import AnchorAmountRescaler
from app.modules.transactions.gateways.base import HTTP_TIMEOUT_S, PaymentHttpClient
from app.modules.transactions.gateways.factory import PaymentGatewayFactory
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.stats_repository import TransactionStatsRepository
from app.modules.transactions.usecases import (
    PruneExpiredTransactionsUseCase,
    ReconcilePaidTransactionsUseCase,
)
from app.modules.transactions.usecases.create_checkout import CreateCheckoutUseCase
from app.modules.transactions.usecases.create_test_payment import CreateTestPaymentUseCase
from app.modules.transactions.usecases.fulfill_transaction import FulfillTransactionUseCase
from app.modules.transactions.usecases.get_test_payment_status import GetTestPaymentStatusUseCase
from app.modules.transactions.usecases.get_transaction import GetTransactionUseCase
from app.modules.transactions.usecases.get_transaction_summary import GetTransactionSummaryUseCase
from app.modules.transactions.usecases.handle_payment_webhook import HandlePaymentWebhookUseCase
from app.modules.transactions.usecases.list_transaction_gateways import (
    ListTransactionGatewaysUseCase,
)
from app.modules.transactions.usecases.list_transactions import ListTransactionsUseCase


class TransactionsProvider(Provider):
    scope = Scope.REQUEST

    transaction_repository = provide(TransactionRepository)
    transaction_stats_repository = provide(TransactionStatsRepository)
    anchor_amount_rescaler = alias(source=TransactionRepository, provides=AnchorAmountRescaler)
    use_cases = provide_all(
        CreateCheckoutUseCase,
        CreateTestPaymentUseCase,
        FulfillTransactionUseCase,
        GetTestPaymentStatusUseCase,
        ListTransactionsUseCase,
        ListTransactionGatewaysUseCase,
        GetTransactionUseCase,
        GetTransactionSummaryUseCase,
        HandlePaymentWebhookUseCase,
        PruneExpiredTransactionsUseCase,
        ReconcilePaidTransactionsUseCase,
    )
    payment_gateway_factory = provide(PaymentGatewayFactory, scope=Scope.APP)

    @provide(scope=Scope.APP)
    async def payment_http_client(self) -> AsyncIterator[PaymentHttpClient]:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_S) as client:
            yield PaymentHttpClient(client)


def get_transactions_providers() -> list[Provider]:
    return [TransactionsProvider()]
