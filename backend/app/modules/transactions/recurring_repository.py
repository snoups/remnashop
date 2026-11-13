from datetime import datetime
from typing import Optional

from loguru import logger
from sqlalchemy import case, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.recurring_payment import RecurringPayment
from app.core.db.models.subscription import Subscription
from app.core.db.models.transaction import Transaction
from app.core.enums import PaymentGatewayType, TransactionStatus
from app.core.utils.time import datetime_now
from app.modules.transactions.recurring_dto import RecurringPaymentDto
from app.modules.transactions.recurring_policy import SAFE_REPOST_WINDOW


class RecurringPaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(
        self, subscription_id: int, *, for_update: bool = False
    ) -> Optional[RecurringPaymentDto]:
        stmt = select(RecurringPayment).where(RecurringPayment.subscription_id == subscription_id)
        if for_update:
            stmt = stmt.with_for_update()
        row = await self.session.scalar(stmt.execution_options(populate_existing=True))
        if row is None:
            return None
        return RecurringPaymentDto(
            subscription_id=row.subscription_id,
            source_transaction_id=row.source_transaction_id,
            payment_method_id=row.payment_method_id,
            shop_id=row.shop_id,
            enabled=row.enabled,
            customer_disabled=row.customer_disabled,
            last_error=row.last_error,
            pending_transaction_id=row.pending_transaction_id,
            attempted_at=row.attempted_at,
        )

    async def list_due(self, now: datetime, *, due_before: datetime, limit: int) -> list[int]:
        ids = await self.session.scalars(
            select(RecurringPayment.subscription_id)
            .join(Subscription, Subscription.id == RecurringPayment.subscription_id)
            .where(
                RecurringPayment.next_attempt_at <= now,
                or_(
                    RecurringPayment.pending_transaction_id.is_not(None),
                    RecurringPayment.enabled.is_(True) & (Subscription.expire_at <= due_before),
                ),
            )
            .order_by(RecurringPayment.next_attempt_at, RecurringPayment.subscription_id)
            .limit(limit)
        )
        return list(ids)

    async def set_enabled(self, subscription_id: int, enabled: bool) -> None:
        now = datetime_now()
        # A tombstone also covers cancellation before the fulfillment event enrolls the order.
        await self.session.execute(
            insert(RecurringPayment)
            .values(
                subscription_id=subscription_id,
                enabled=enabled,
                customer_disabled=not enabled,
                disabled_at=None if enabled else now,
                last_error=None if enabled else "customer_disabled",
                next_attempt_at=now,
            )
            .on_conflict_do_update(
                index_elements=[RecurringPayment.subscription_id],
                set_={
                    # Only a new successful manual payment can supersede an
                    # unknown debit; toggling the preference must not erase it.
                    "enabled": case(
                        (RecurringPayment.last_error == "payment_status_unknown", False),
                        else_=enabled,
                    ),
                    "customer_disabled": not enabled,
                    "disabled_at": None if enabled else now,
                    "last_error": case(
                        (
                            RecurringPayment.last_error == "payment_status_unknown",
                            "payment_status_unknown",
                        ),
                        else_=None if enabled else "customer_disabled",
                    ),
                    "next_attempt_at": now,
                    "updated_at": now,
                },
            )
        )

    async def defer(
        self, subscription_id: int, until: datetime, error: Optional[str] = None
    ) -> None:
        values: dict[str, object] = {"next_attempt_at": until}
        if error is not None:
            values["last_error"] = error
        await self.session.execute(
            update(RecurringPayment)
            .where(RecurringPayment.subscription_id == subscription_id)
            .values(**values)
        )

    async def disable(self, subscription_id: int, reason: str) -> None:
        await self.session.execute(
            update(RecurringPayment)
            .where(RecurringPayment.subscription_id == subscription_id)
            .values(enabled=False, disabled_at=datetime_now(), last_error=reason)
        )

    async def set_pending(self, subscription_id: int, transaction_id: int) -> None:
        await self.session.execute(
            update(RecurringPayment)
            .where(RecurringPayment.subscription_id == subscription_id)
            .values(pending_transaction_id=transaction_id, attempted_at=None)
        )

    async def fail_pending(self, subscription_id: int, reason: str) -> None:
        await self.session.execute(
            update(RecurringPayment)
            .where(RecurringPayment.subscription_id == subscription_id)
            .values(
                enabled=False,
                disabled_at=datetime_now(),
                last_error=reason,
                pending_transaction_id=None,
                attempted_at=None,
            )
        )

    async def retire_pending(
        self,
        subscription_id: int,
        transaction_id: Optional[int] = None,
        *,
        force_unknown: bool = False,
    ) -> bool:
        if transaction_id is None:
            current = await self.get(subscription_id)
            if current is None or current.pending_transaction_id is None:
                return False
            transaction_id = current.pending_transaction_id
        return await self._retire_pending_order(
            subscription_id, transaction_id, force_unknown=force_unknown
        )

    async def _retire_pending_order(
        self, subscription_id: int, transaction_id: int, *, force_unknown: bool
    ) -> bool:
        # Fulfillment locks the order before the mandate. Keeping that order here
        # lets a concurrent verified webhook win without a lock inversion.
        order = await self.session.get(
            Transaction, transaction_id, with_for_update=True, populate_existing=True
        )
        if (
            order is None
            or not order.is_recurring
            or order.target_subscription_id != subscription_id
            or order.status is TransactionStatus.PAID
        ):
            return False
        if order.status is TransactionStatus.PENDING and order.external_payment_id is not None:
            return False
        row = await self.session.scalar(
            select(RecurringPayment)
            .where(RecurringPayment.subscription_id == subscription_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None or row.pending_transaction_id != transaction_id:
            return False
        now = datetime_now()
        unknown = order.status is TransactionStatus.PENDING
        if unknown and not (
            force_unknown
            or row.last_error == "payment_status_unknown"
            or order.created_at <= now - SAFE_REPOST_WINDOW
        ):
            return False
        if unknown:
            # FAILED closes our local attempt; it does not assert a bank refusal.
            # The order/key remain available for a late verified success webhook.
            order.status = TransactionStatus.FAILED
        source = (
            await self.session.get(Transaction, row.source_transaction_id, populate_existing=True)
            if row.source_transaction_id is not None
            else None
        )
        reconnected = bool(
            source and source.fulfilled_at is not None and source.fulfilled_at >= order.created_at
        )
        row.pending_transaction_id = None
        row.attempted_at = None
        row.next_attempt_at = now
        if not reconnected:
            row.enabled = False
            row.disabled_at = now
            row.last_error = (
                "payment_status_unknown" if unknown else row.last_error or "payment_canceled"
            )
        await self.session.flush()
        logger.warning(
            f"Retired recurring order '{transaction_id}' for subscription '{subscription_id}'; "
            f"provider outcome unknown: {unknown}, newer manual enrollment: {reconnected}"
        )
        return True

    async def mark_attempted(self, subscription_id: int) -> None:
        await self.session.execute(
            update(RecurringPayment)
            .where(
                RecurringPayment.subscription_id == subscription_id,
                RecurringPayment.attempted_at.is_(None),
            )
            .values(attempted_at=datetime_now())
        )

    async def on_fulfilled(self, order: Transaction, subscription_id: int) -> None:
        now = datetime_now()
        if order.is_recurring:
            await self.session.execute(
                update(RecurringPayment)
                .where(RecurringPayment.pending_transaction_id == order.id)
                .values(
                    pending_transaction_id=None,
                    attempted_at=None,
                    next_attempt_at=now,
                    last_error=case(
                        (RecurringPayment.customer_disabled.is_(True), "customer_disabled"),
                        else_=None,
                    ),
                )
            )
            return
        await self.retire_pending(subscription_id)
        previous = (
            await self.get(order.target_subscription_id)
            if order.target_subscription_id is not None
            and order.target_subscription_id != subscription_id
            else None
        )
        if previous is not None and previous.customer_disabled:
            await self.set_enabled(subscription_id, False)
        if not order.recurring_consent and await self.get(subscription_id) is None:
            return
        # Serializes enrollment of two manual payments for the same subscription.
        await self.session.execute(
            insert(RecurringPayment)
            .values(subscription_id=subscription_id, enabled=False, next_attempt_at=now)
            .on_conflict_do_nothing(index_elements=[RecurringPayment.subscription_id])
        )
        row = await self.session.scalar(
            select(RecurringPayment)
            .where(RecurringPayment.subscription_id == subscription_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None or (row.source_transaction_id or 0) >= order.id:
            return
        if order.gateway_type is not PaymentGatewayType.YOOKASSA or not order.recurring_consent:
            row.enabled = False
            if not row.customer_disabled:
                row.last_error = "manual_payment"
            return
        if order.status is not TransactionStatus.PAID or order.is_test:
            return
        opted_out = row.customer_disabled
        row.source_transaction_id = order.id
        row.payment_method_id = order.saved_payment_method_id
        row.shop_id = order.payment_method_shop_id or ""
        row.enabled = bool(row.payment_method_id) and not opted_out
        row.last_error = (
            "customer_disabled"
            if opted_out
            else None
            if row.enabled
            else "payment_method_not_saved"
        )
        row.next_attempt_at = now
        await self.session.flush()
