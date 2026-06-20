from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Self
from uuid import UUID

from src.core.enums import Currency, PaymentGatewayType, PurchaseType, TransactionStatus

from .base import BaseDto, TimestampMixin, TrackableMixin
from .plan import PlanSnapshotDto


@dataclass(kw_only=True)
class PriceDetailsDto(TrackableMixin):
    original_amount: Decimal
    discount_percent: int
    final_amount: Decimal

    @property
    def is_free(self) -> bool:
        return self.final_amount == 0

    @classmethod
    def test(cls) -> Self:
        return cls(
            original_amount=Decimal(2),
            discount_percent=0,
            final_amount=Decimal(2),
        )


@dataclass(kw_only=True)
class TransactionDto(BaseDto, TrackableMixin, TimestampMixin):
    payment_id: UUID
    user_telegram_id: Optional[int]

    status: TransactionStatus
    is_test: bool = False

    purchase_type: PurchaseType
    gateway_type: PaymentGatewayType

    pricing: "PriceDetailsDto"
    currency: Currency
    plan_snapshot: "PlanSnapshotDto"

    promocode_id: Optional[int] = field(default=None)

    @property
    def is_completed(self) -> bool:
        return self.status == TransactionStatus.COMPLETED
