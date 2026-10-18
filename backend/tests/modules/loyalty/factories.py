from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from typing import Any, Final
from uuid import uuid4

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.transaction import Transaction
from app.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PurchaseChannel,
    PurchaseType,
    TransactionStatus,
)
from app.core.utils.time import datetime_now
from app.modules.loyalty.dto import LoyaltyTierDto, UpdateLoyaltySettingsDto
from app.modules.loyalty.repository import LoyaltyRepository
from app.modules.transactions import TransactionRepository
from app.modules.transactions.dto import CreateTransactionDto
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.modules.subscriptions.factories import make_plan_snapshot

TIERS: Final[list[LoyaltyTierDto]] = [
    LoyaltyTierDto(threshold=Decimal("100"), percent=3),
    LoyaltyTierDto(threshold=Decimal("500"), percent=10),
]


async def save_settings(session: AsyncSession, **overrides: Any) -> None:
    data = UpdateLoyaltySettingsDto(enabled=True, window_months=12, tiers=TIERS)
    await LoyaltyRepository(session).save_settings(replace(data, **overrides))


async def paid_order(session: AsyncSession, user_id: int, amount: str, *, days_ago: int = 1) -> int:
    order = await TransactionRepository(session).create(
        CreateTransactionDto(
            channel=PurchaseChannel.CABINET,
            user_id=user_id,
            plan_id=None,
            plan_snapshot=make_plan_snapshot(),
            duration_days=30,
            currency=Currency.USD,
            purchase_type=PurchaseType.NEW,
            target_subscription_id=None,
            gateway_type=PaymentGatewayType.YOOKASSA,
            base_price=Decimal(amount),
            discount_percent=0,
            discount_source=DiscountSource.NONE,
            final_price=Decimal(amount),
            anchor_base_price=Decimal(amount),
            anchor_final_price=Decimal(amount),
            customer_email=None,
            idempotency_key=uuid4().hex,
            expires_at=datetime_now(),
        )
    )
    await session.execute(
        update(Transaction)
        .where(Transaction.id == order.id)
        .values(status=TransactionStatus.PAID, updated_at=datetime_now() - timedelta(days=days_ago))
    )
    return order.id


async def make_user(user_repository: UserRepository, telegram_id: int) -> int:
    return (await user_repository.create(CreateUserDto(name="u", telegram_id=telegram_id))).id
