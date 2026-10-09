from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin
from app.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PurchaseType,
    TransactionStatus,
)


class Transaction(BaseSql, TimestampMixin):
    __tablename__ = "transactions"
    __table_args__ = (
        # Backs the prune_expired_transactions cron sweep's status+expires_at scan.
        Index("ix_transactions_status_expires_at", "status", "expires_at"),
        # Per gateway, not global: providers mint their own id namespaces and
        # two of them handing out the same id must not collide (it would fail
        # the checkout that writes the second one, leaving a payment the
        # customer can still complete against an order with no external id).
        UniqueConstraint(
            "gateway_type", "external_payment_id", name="ux_transactions_gateway_external_id"
        ),
    )

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
    external_payment_id: Mapped[Optional[str]] = mapped_column(String(128))
    status: Mapped[TransactionStatus] = mapped_column(
        default=TransactionStatus.PENDING, server_default="PENDING"
    )

    base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    discount_percent: Mapped[int] = mapped_column(default=0, server_default="0")
    discount_source: Mapped[DiscountSource] = mapped_column(
        default=DiscountSource.NONE, server_default="NONE"
    )
    # the PURCHASE discount came from a promocode (admin-granted ones are always handed back)
    discount_from_promocode: Mapped[bool] = mapped_column(default=False, server_default="false")
    # the plan's own promotion, applied before discount_percent
    plan_discount_percent: Mapped[int] = mapped_column(default=0, server_default="0")
    final_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    anchor_base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    anchor_final_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    discount_promocode_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("promocodes.id", ondelete="SET NULL"), index=True
    )

    customer_email: Mapped[Optional[str]] = mapped_column(String(255))
    idempotency_key: Mapped[str] = mapped_column(String(36), unique=True)

    expires_at: Mapped[datetime]
    # Set by reconcile_paid_transactions once a PAID order's subscription is found --
    # the durable "provisioned" record, unlike the idempotency key it's read
    # from (pruned after IDEMPOTENCY_KEY_RETENTION_DAYS).
    fulfilled_at: Mapped[Optional[datetime]]
    # the subscription this order provisioned, recorded with fulfilled_at --
    # a NEW order has no target_subscription_id to tell it otherwise
    fulfilled_subscription_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="SET NULL")
    )
    # Dashboard gateway check: never provisioned, excluded from every revenue query.
    is_test: Mapped[bool] = mapped_column(default=False, server_default="false")
