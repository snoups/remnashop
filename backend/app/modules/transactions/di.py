from collections.abc import AsyncIterator
from typing import cast

import httpx
from dishka import Provider, Scope, alias, provide, provide_all

from app.core.ports import AnchorAmountRescaler, OpenOrderCounter, OrderFailer
from app.modules.transactions.dispatch import ConfirmStarsPaymentDispatch
from app.modules.transactions.gateways.base import HTTP_TIMEOUT_S, PaymentHttpClient
from app.modules.transactions.gateways.factory import PaymentGatewayFactory
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.stats_repository import TransactionStatsRepository
from app.modules.transactions.tasks import confirm_stars_payment_task
from app.modules.transactions.usecases import (
    ConfirmStarsPaymentUseCase,
    CreateCheckoutUseCase,
    CreateTestPaymentUseCase,
    FulfillTransactionUseCase,
    GetPaymentWaitlistCountUseCase,
    GetTestPaymentStatusUseCase,
    GetTransactionSummaryUseCase,
    GetTransactionUseCase,
    HandlePaymentWebhookUseCase,
    ListPaymentMethodsUseCase,
    ListTransactionGatewaysUseCase,
    ListTransactionsUseCase,
    NotifyPaymentWaitlistUseCase,
    PruneExpiredTransactionsUseCase,
    ReconcilePaidTransactionsUseCase,
    ValidateStarsPreCheckoutUseCase,
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
        ListPaymentMethodsUseCase,
        ListTransactionGatewaysUseCase,
        GetTransactionUseCase,
        GetTransactionSummaryUseCase,
        GetPaymentWaitlistCountUseCase,
        HandlePaymentWebhookUseCase,
        NotifyPaymentWaitlistUseCase,
        PruneExpiredTransactionsUseCase,
        ReconcilePaidTransactionsUseCase,
        ConfirmStarsPaymentUseCase,
        ValidateStarsPreCheckoutUseCase,
    )
    payment_gateway_factory = provide(PaymentGatewayFactory, scope=Scope.APP)

    @provide(scope=Scope.APP)
    async def payment_http_client(self) -> AsyncIterator[PaymentHttpClient]:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_S) as client:
            yield PaymentHttpClient(client)

    @provide(scope=Scope.APP)
    def confirm_stars_payment_dispatch(self) -> ConfirmStarsPaymentDispatch:
        return cast(ConfirmStarsPaymentDispatch, confirm_stars_payment_task)


def get_transactions_providers() -> list[Provider]:
    return [TransactionsProvider()]
