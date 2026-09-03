from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin
from app.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PaymentOrderStatus,
    PurchaseType,
)


class PaymentOrder(BaseSql, TimestampMixin):
    __tablename__ = "payment_orders"
    # Backs the prune_expired_payment_orders cron sweep's status+expires_at scan.
    __table_args__ = (Index("ix_payment_orders_status_expires_at", "status", "expires_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # SET NULL, not RESTRICT: purchase_subscription_task provisions entirely
    # from plan_snapshot (captured at checkout time, includes squads/limits) --
    # it never re-resolves plan_id via PlanRepository, even while a PAID order
    # is still awaiting provisioning. Unlike Promocode.reward_plan_id (which
    # IS resolved live, synchronously, at redemption time), nothing here reads
    # plan_id for anything but display once the order exists.
    plan_id: Mapped[Optional[int]] = mapped_column(ForeignKey("plans.id", ondelete="SET NULL"))
    plan_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    duration_days: Mapped[int]
    currency: Mapped[Currency]
    purchase_type: Mapped[PurchaseType]
    target_subscription_id: Mapped[Optional[int]] = mapped_column(ForeignKey("subscriptions.id"))

    gateway_type: Mapped[PaymentGatewayType]
    external_payment_id: Mapped[Optional[str]] = mapped_column(String(128), unique=True)
    status: Mapped[PaymentOrderStatus] = mapped_column(
        default=PaymentOrderStatus.PENDING, server_default="PENDING"
    )

    base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    discount_percent: Mapped[int] = mapped_column(default=0, server_default="0")
    discount_source: Mapped[DiscountSource] = mapped_column(
        default=DiscountSource.NONE, server_default="NONE"
    )
    final_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    customer_email: Mapped[Optional[str]] = mapped_column(String(255))
    idempotency_key: Mapped[str] = mapped_column(String(36), unique=True)

    expires_at: Mapped[datetime]
