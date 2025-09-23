from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .plan import PlanSnapshotDto
    from .user import UserDto

from datetime import datetime
from uuid import UUID

from pydantic import Field

from src.core.enums import Currency, PaymentGatewayType, TransactionStatus

from .base import TrackableDto


class TransactionDto(TrackableDto):
    id: Optional[int] = Field(default=None, frozen=True)
    payment_id: UUID

    status: TransactionStatus
    gateway: PaymentGatewayType
    amount: Decimal
    currency: Currency
    plan: "PlanSnapshotDto"

    user: Optional["UserDto"] = None

    created_at: Optional[datetime] = Field(default=None, frozen=True)
    updated_at: Optional[datetime] = Field(default=None, frozen=True)
