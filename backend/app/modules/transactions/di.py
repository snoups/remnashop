from collections.abc import AsyncIterator

import httpx
from dishka import Provider, Scope, alias, provide, provide_all

from app.core.ports import AnchorAmountRescaler, OpenOrderCounter, OrderFailer
from app.modules.transactions.gateways.base import HTTP_TIMEOUT_S, PaymentHttpClient
from app.modules.transactions.gateways.factory import PaymentGatewayFactory
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.stats_repository import TransactionStatsRepository
from app.modules.transactions.usecases import (
    CreateCheckoutUseCase,
    CreateTestPaymentUseCase,
    FulfillTransactionUseCase,
    GetPaymentWaitlistCountUseCase,
    GetTestPaymentStatusUseCase,
    GetTransactionSummaryUseCase,
    GetTransactionUseCase,
    HandlePaymentWebhookUseCase,
    ListTransactionGatewaysUseCase,
    ListTransactionsUseCase,
    NotifyPaymentWaitlistUseCase,
    PruneExpiredTransactionsUseCase,
    ReconcilePaidTransactionsUseCase,
)
from app.modules.transactions.waitlist_repository import WaitlistClaims, WaitlistRepository


class TransactionsProvider(Provider):
    scope = Scope.REQUEST

    transaction_repository = provide(TransactionRepository)
    transaction_stats_repository = provide(TransactionStatsRepository)
    waitlist_repository = provide(WaitlistRepository)
    waitlist_claims = provide(WaitlistClaims, scope=Scope.APP)
    anchor_amount_rescaler = alias(source=TransactionRepository, provides=AnchorAmountRescaler)
    order_failer = alias(source=TransactionRepository, provides=OrderFailer)
    open_order_counter = alias(source=TransactionRepository, provides=OpenOrderCounter)
    use_cases = provide_all(
        CreateCheckoutUseCase,
        CreateTestPaymentUseCase,
        FulfillTransactionUseCase,
        GetTestPaymentStatusUseCase,
        ListTransactionsUseCase,
        ListTransactionGatewaysUseCase,
        GetTransactionUseCase,
        GetTransactionSummaryUseCase,
        GetPaymentWaitlistCountUseCase,
        HandlePaymentWebhookUseCase,
        NotifyPaymentWaitlistUseCase,
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
