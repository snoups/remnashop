from collections.abc import AsyncIterator
from typing import cast

import httpx
from dishka import Provider, Scope, alias, provide, provide_all

from app.modules.plans import AnchorAmountRescaler
from app.modules.subscriptions import OpenOrderCounter, OrderFailer, RecurringPaymentCloser
from app.modules.transactions.checkout_pricing import CheckoutPricer
from app.modules.transactions.dispatch import (
    ConfirmStarsPaymentDispatch,
    ProcessRecurringPaymentDispatch,
)
from app.modules.transactions.gateways.base import HTTP_TIMEOUT_S, PaymentHttpClient
from app.modules.transactions.gateways.factory import PaymentGatewayFactory
from app.modules.transactions.recurring_admin_repository import RecurringPaymentAdminRepository
from app.modules.transactions.recurring_repository import RecurringPaymentRepository
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.stats_repository import TransactionStatsRepository
from app.modules.transactions.tasks import (
    confirm_stars_payment_task,
    process_one_recurring_payment_task,
)
from app.modules.transactions.usecases import (
    CheckTransactionPaymentUseCase,
    ConfirmStarsPaymentUseCase,
    CreateCheckoutUseCase,
    CreateTestPaymentUseCase,
    EnqueueRecurringPaymentsUseCase,
    FulfillTransactionUseCase,
    GetOwnRecurringPaymentUseCase,
    GetOwnTransactionUseCase,
    GetPaymentWaitlistCountUseCase,
    GetTestPaymentStatusUseCase,
    GetTransactionSummaryUseCase,
    GetTransactionUseCase,
    HandlePaymentWebhookUseCase,
    JoinPaymentWaitlistUseCase,
    ListOwnTransactionsUseCase,
    ListPaymentMethodsUseCase,
    ListTransactionGatewaysUseCase,
    ListTransactionsUseCase,
    ListUnratedAnchorAmountsUseCase,
    MarkOrderFulfilledUseCase,
    NotifyPaymentWaitlistUseCase,
    PreviewRefundUseCase,
    ProcessRecurringPaymentsUseCase,
    PruneExpiredTransactionsUseCase,
    QuoteCheckoutUseCase,
    RateUnratedAnchorAmountsUseCase,
    ReconcilePaidTransactionsUseCase,
    RefundTransactionUseCase,
    SetOwnRecurringPaymentUseCase,
    ValidateStarsPreCheckoutUseCase,
)
from app.modules.transactions.usecases.get_recurring_terms import GetCheckoutRecurringTermsUseCase
from app.modules.transactions.usecases.list_recurring_payments import ListRecurringPaymentsUseCase
from app.modules.transactions.usecases.manage_recurring_payment import ManageRecurringPaymentUseCase
from app.modules.transactions.waitlist_repository import WaitlistClaims, WaitlistRepository


class TransactionsProvider(Provider):
    scope = Scope.REQUEST

    transaction_repository = provide(TransactionRepository)
    recurring_repository = provide(RecurringPaymentRepository)
    recurring_closer = alias(source=RecurringPaymentRepository, provides=RecurringPaymentCloser)
    recurring_admin_repository = provide(RecurringPaymentAdminRepository)
    transaction_stats_repository = provide(TransactionStatsRepository)
    waitlist_repository = provide(WaitlistRepository)
    waitlist_claims = provide(WaitlistClaims, scope=Scope.APP)
    checkout_pricer = provide(CheckoutPricer)
    anchor_amount_rescaler = alias(source=TransactionRepository, provides=AnchorAmountRescaler)
    order_failer = alias(source=TransactionRepository, provides=OrderFailer)
    open_order_counter = alias(source=TransactionRepository, provides=OpenOrderCounter)
    use_cases = provide_all(
        CreateCheckoutUseCase,
        EnqueueRecurringPaymentsUseCase,
        ListRecurringPaymentsUseCase,
        ManageRecurringPaymentUseCase,
        GetCheckoutRecurringTermsUseCase,
        GetOwnRecurringPaymentUseCase,
        SetOwnRecurringPaymentUseCase,
        ProcessRecurringPaymentsUseCase,
        QuoteCheckoutUseCase,
        RateUnratedAnchorAmountsUseCase,
        CreateTestPaymentUseCase,
        CheckTransactionPaymentUseCase,
        FulfillTransactionUseCase,
        GetTestPaymentStatusUseCase,
        ListTransactionsUseCase,
        ListUnratedAnchorAmountsUseCase,
        ListOwnTransactionsUseCase,
        GetOwnTransactionUseCase,
        ListPaymentMethodsUseCase,
        ListTransactionGatewaysUseCase,
        GetTransactionUseCase,
        GetTransactionSummaryUseCase,
        GetPaymentWaitlistCountUseCase,
        JoinPaymentWaitlistUseCase,
        HandlePaymentWebhookUseCase,
        NotifyPaymentWaitlistUseCase,
        PruneExpiredTransactionsUseCase,
        ReconcilePaidTransactionsUseCase,
        MarkOrderFulfilledUseCase,
        ConfirmStarsPaymentUseCase,
        ValidateStarsPreCheckoutUseCase,
        PreviewRefundUseCase,
        RefundTransactionUseCase,
    )
    payment_gateway_factory = provide(PaymentGatewayFactory, scope=Scope.APP)

    @provide(scope=Scope.APP)
    async def payment_http_client(self) -> AsyncIterator[PaymentHttpClient]:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_S) as client:
            yield PaymentHttpClient(client)

    @provide(scope=Scope.APP)
    def process_recurring_payment_dispatch(self) -> ProcessRecurringPaymentDispatch:
        return cast(ProcessRecurringPaymentDispatch, process_one_recurring_payment_task)

    @provide(scope=Scope.APP)
    def confirm_stars_payment_dispatch(self) -> ConfirmStarsPaymentDispatch:
        return cast(ConfirmStarsPaymentDispatch, confirm_stars_payment_task)


def get_transactions_providers() -> list[Provider]:
    return [TransactionsProvider()]
