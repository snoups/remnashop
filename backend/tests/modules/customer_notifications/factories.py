from datetime import timedelta
from decimal import Decimal

from app.core.db.uow import UnitOfWork
from app.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PaymentOutcome,
    PurchaseChannel,
    PurchaseType,
)
from app.core.utils.time import datetime_now
from app.modules.transactions import TransactionRepository
from app.modules.transactions.dto import CreateTransactionDto, TransactionDto
from tests.modules.subscriptions.factories import make_plan_snapshot


class FakeBotSignals:
    def __init__(self, receivers: int = 1) -> None:
        self.receivers = receivers
        self.outcomes: list[tuple[int, int, PaymentOutcome]] = []

    async def payment_outcome(
        self, telegram_id: int, order_id: int, outcome: PaymentOutcome
    ) -> int:
        self.outcomes.append((telegram_id, order_id, outcome))
        return self.receivers


async def create_order(
    repository: TransactionRepository,
    uow: UnitOfWork,
    *,
    user_id: int,
    channel: PurchaseChannel,
    key: str,
) -> TransactionDto:
    async with uow:
        order = await repository.create(
            CreateTransactionDto(
                channel=channel,
                user_id=user_id,
                plan_id=None,
                plan_snapshot=make_plan_snapshot(),
                duration_days=30,
                currency=Currency.RUB,
                purchase_type=PurchaseType.NEW,
                target_subscription_id=None,
                gateway_type=PaymentGatewayType.YOOKASSA,
                base_price=Decimal("500"),
                discount_percent=0,
                discount_source=DiscountSource.NONE,
                final_price=Decimal("500"),
                anchor_base_price=Decimal("500"),
                anchor_final_price=Decimal("500"),
                customer_email=None,
                idempotency_key=key,
                expires_at=datetime_now() + timedelta(minutes=30),
            )
        )
        await uow.commit()
    return order
