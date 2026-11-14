from datetime import datetime, timedelta
from typing import Optional

from loguru import logger
from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.recurring_consent import RecurringConsent
from app.core.db.models.recurring_payment import RecurringPayment
from app.core.db.models.subscription import Subscription
from app.core.db.models.transaction import Transaction
from app.core.enums import PaymentGatewayType, PurchaseChannel, TransactionStatus
from app.core.utils.time import datetime_now
from app.modules.transactions.recurring_dto import RecurringPaymentDto
from app.modules.transactions.recurring_events import (
    RecurringPaymentExhaustedEvent,
    RecurringPaymentFailedEvent,
    RecurringPaymentPausedEvent,
    RecurringPaymentUpcomingEvent,
    persist_recurring_event,
)
from app.modules.transactions.recurring_policy import (
    POLICY_RECHECK_DELAY,
    SAFE_REPOST_WINDOW,
    RecurringReason,
    recurring_reason,
)
from app.modules.transactions.recurring_queries import renewal_window_expired
from app.modules.transactions.recurring_terms import RecurringTerms


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
            submitted_at=row.submitted_at,
            disabled_at=row.disabled_at,
            consent_id=row.consent_id,
            first_failure_at=row.first_failure_at,
            retry_count=row.retry_count,
            cycle_expire_at=row.cycle_expire_at,
            pending_since=row.pending_since,
            upcoming_notified_for=row.upcoming_notified_for,
            next_attempt_at=row.next_attempt_at,
            leased_until=row.leased_until,
            bank_retry_at=row.bank_retry_at,
        )

    async def list_due(
        self,
        now: datetime,
        *,
        due_before: datetime,
        limit: int,
        pending: Optional[bool] = None,
        claim_until: Optional[datetime] = None,
    ) -> list[int]:
        await self.close_overdue(now, limit=limit)
        statement = (
            select(RecurringPayment.subscription_id)
            .join(Subscription, Subscription.id == RecurringPayment.subscription_id)
            .outerjoin(RecurringConsent, RecurringConsent.id == RecurringPayment.consent_id)
            .where(
                RecurringPayment.next_attempt_at <= now,
                or_(RecurringPayment.leased_until.is_(None), RecurringPayment.leased_until <= now),
                or_(
                    RecurringPayment.pending_transaction_id.is_not(None),
                    and_(
                        RecurringPayment.enabled.is_(True),
                        Subscription.expire_at <= due_before,
                        ~renewal_window_expired(now),
                        or_(
                            RecurringPayment.last_error.is_(None),
                            RecurringPayment.last_error.not_in(
                                [
                                    reason.value
                                    for reason in RecurringReason
                                    if not reason.policy.allows_debit
                                ]
                            ),
                        ),
                    ),
                ),
            )
            .order_by(RecurringPayment.next_attempt_at, RecurringPayment.subscription_id)
            .limit(limit)
        )
        if pending is not None:
            statement = statement.where(
                RecurringPayment.pending_transaction_id.is_not(None)
                if pending
                else RecurringPayment.pending_transaction_id.is_(None)
            )
        if claim_until is not None:
            statement = statement.with_for_update(of=RecurringPayment, skip_locked=True)
        ids = list(await self.session.scalars(statement))
        if ids and claim_until is not None:
            await self.session.execute(
                update(RecurringPayment)
                .where(RecurringPayment.subscription_id.in_(ids))
                .values(leased_until=claim_until)
            )
        return ids

    async def close_overdue(self, now: datetime, *, limit: int) -> None:
        ids = list(
            await self.session.scalars(
                select(RecurringPayment.subscription_id)
                .join(Subscription, Subscription.id == RecurringPayment.subscription_id)
                .outerjoin(RecurringConsent, RecurringConsent.id == RecurringPayment.consent_id)
                .where(
                    RecurringPayment.enabled.is_(True),
                    RecurringPayment.pending_transaction_id.is_(None),
                    renewal_window_expired(now),
                )
                .order_by(Subscription.expire_at, RecurringPayment.subscription_id)
                .limit(limit)
                .with_for_update(of=RecurringPayment, skip_locked=True)
            )
        )
        for subscription_id in ids:
            current = await self.get(subscription_id)
            reason = recurring_reason(current.last_error) if current else None
            await self.disable(
                subscription_id,
                reason
                if reason and reason.policy.terminal
                else RecurringReason.RENEWAL_WINDOW_EXPIRED,
            )

    async def notify_upcoming(
        self,
        subscription_id: int,
        expire_at: datetime,
        terms: RecurringTerms,
        scheduled_at: datetime,
    ) -> None:
        row = await self.session.get(
            RecurringPayment, subscription_id, with_for_update=True, populate_existing=True
        )
        if row is None or row.upcoming_notified_for == expire_at:
            return
        row.upcoming_notified_for = expire_at
        row.leased_until = None
        await persist_recurring_event(
            self.session,
            RecurringPaymentUpcomingEvent(
                user_id=terms.user_id,
                subscription_id=subscription_id,
                amount=str(terms.amount_limit),
                currency=terms.currency,
                scheduled_at=scheduled_at.isoformat(),
            ),
        )

    async def record_consent(
        self,
        terms: RecurringTerms,
        *,
        channel: PurchaseChannel,
        telegram_id: Optional[int],
        event_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> int:
        consent = RecurringConsent(
            user_id=terms.user_id,
            owner_user_id=terms.user_id,
            subscription_id=terms.target_subscription_id,
            channel=channel.value,
            telegram_id=telegram_id,
            event_id=event_id,
            ip_address=ip_address,
            terms=terms.model_dump(mode="json"),
            accepted_at=datetime_now(),
        )
        self.session.add(consent)
        await self.session.flush()
        return consent.id

    async def consent_terms(self, consent_id: Optional[int]) -> Optional[RecurringTerms]:
        consent = (
            await self.session.get(RecurringConsent, consent_id, populate_existing=True)
            if consent_id is not None
            else None
        )
        if consent is None or consent.revoked_at is not None:
            return None
        try:
            # Ownership follows a verified account merge. The stored author/text never change.
            return RecurringTerms.model_validate(consent.terms).model_copy(
                update={"user_id": consent.owner_user_id}
            )
        except ValueError:
            return None

    async def revoke_consent(
        self,
        subscription_id: int,
        *,
        channel: PurchaseChannel,
        event_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        # The mandate lock serializes withdrawal with the worker's outgoing request.
        mandate = await self.get(subscription_id, for_update=True)
        if mandate is None or mandate.consent_id is None:
            return
        await self.revoke_consent_id(
            mandate.consent_id, channel=channel, event_id=event_id, ip_address=ip_address
        )

    async def revoke_consent_id(
        self,
        consent_id: Optional[int],
        *,
        channel: PurchaseChannel,
        event_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        if consent_id is None:
            return
        await self.session.execute(
            update(RecurringConsent)
            .where(RecurringConsent.id == consent_id, RecurringConsent.revoked_at.is_(None))
            .values(
                revoked_at=datetime_now(),
                revoked_channel=channel.value,
                revoked_event_id=event_id,
                revoked_ip_address=ip_address,
            )
        )

    async def set_enabled(
        self,
        subscription_id: int,
        enabled: bool,
        *,
        consent_id: Optional[int] = None,
        disabled_at: Optional[datetime] = None,
    ) -> None:
        now = datetime_now()
        await self.session.execute(
            insert(RecurringPayment)
            .values(subscription_id=subscription_id, enabled=False, next_attempt_at=now)
            .on_conflict_do_nothing(index_elements=[RecurringPayment.subscription_id])
        )
        row = await self.session.get(
            RecurringPayment, subscription_id, with_for_update=True, populate_existing=True
        )
        if row is None:
            return
        unknown = row.submitted_at is not None and row.pending_transaction_id is None
        row.consent_id = consent_id
        row.customer_disabled = not enabled
        row.enabled = enabled and consent_id is not None and not unknown
        row.disabled_at = None if enabled else disabled_at or now
        row.last_error = (
            RecurringReason.CUSTOMER_DISABLED
            if not enabled
            else RecurringReason.PAYMENT_STATUS_UNKNOWN
            if unknown
            else None
        )
        row.leased_until = None
        row.next_attempt_at = now
        if enabled and consent_id is not None and not unknown:
            row.bank_retry_at = None
            row.first_failure_at = None
            row.retry_count = 0
        await self.session.flush()

    async def defer(
        self, subscription_id: int, until: datetime, error: Optional[str] = None
    ) -> None:
        row = await self.session.get(
            RecurringPayment, subscription_id, with_for_update=True, populate_existing=True
        )
        if row is None:
            return
        if row.customer_disabled:
            row.last_error = RecurringReason.CUSTOMER_DISABLED
        elif error is not None:
            await self._notice_pause(subscription_id, error, until)
            row.last_error = error
        row.next_attempt_at = until
        row.leased_until = None
        await self.session.flush()

    async def _notice_pause(
        self, subscription_id: int, reason: str, until: Optional[datetime] = None
    ) -> None:
        row = await self.get(subscription_id, for_update=True)
        if row is None or row.customer_disabled or row.last_error == reason:
            return
        subscription = await self.session.get(Subscription, subscription_id)
        if subscription is not None:
            await persist_recurring_event(
                self.session,
                RecurringPaymentPausedEvent(
                    user_id=subscription.user_id,
                    subscription_id=subscription_id,
                    reason=reason,
                    order_id=row.pending_transaction_id,
                    next_attempt_at=until.isoformat() if until is not None else None,
                ),
            )

    async def pause(
        self, subscription_id: int, reason: str, *, until: Optional[datetime] = None
    ) -> None:
        until = until or datetime_now() + POLICY_RECHECK_DELAY
        await self.defer(subscription_id, until, reason)

    async def resume(self, subscription_id: int) -> None:
        await self.session.execute(
            update(RecurringPayment)
            .where(
                RecurringPayment.subscription_id == subscription_id,
                RecurringPayment.customer_disabled.is_(False),
                RecurringPayment.pending_transaction_id.is_(None),
                RecurringPayment.submitted_at.is_(None),
            )
            .values(
                enabled=True,
                disabled_at=None,
                last_error=None,
                next_attempt_at=datetime_now(),
                leased_until=None,
            )
        )

    async def clear_error(self, subscription_id: int) -> None:
        await self.session.execute(
            update(RecurringPayment)
            .where(RecurringPayment.subscription_id == subscription_id)
            .values(
                last_error=case(
                    (RecurringPayment.customer_disabled, RecurringReason.CUSTOMER_DISABLED),
                    else_=None,
                ),
                leased_until=None,
            )
        )

    async def disable(self, subscription_id: int, reason: str) -> None:
        row = await self.session.get(
            RecurringPayment, subscription_id, with_for_update=True, populate_existing=True
        )
        if row is None:
            return
        await self._notice_pause(subscription_id, reason)
        row.enabled = False
        row.leased_until = None
        if not row.customer_disabled:
            row.disabled_at = datetime_now()
            row.last_error = reason
        await self.session.flush()

    async def close_for_plan_change(self, subscription_id: int) -> None:
        current = await self.get(subscription_id)
        if current is None:
            return
        if current.pending_transaction_id is not None:
            await self.session.get(
                Transaction, current.pending_transaction_id, with_for_update=True
            )
        row = await self.session.get(
            RecurringPayment, subscription_id, with_for_update=True, populate_existing=True
        )
        if row is None:
            return
        if row.consent_id is not None:
            await self.session.execute(
                update(RecurringConsent)
                .where(RecurringConsent.id == row.consent_id, RecurringConsent.revoked_at.is_(None))
                .values(revoked_at=datetime_now(), revoked_channel="plan_change")
            )
        await self.disable(subscription_id, RecurringReason.SUBSCRIPTION_CHANGED)

    async def set_pending(
        self, subscription_id: int, transaction_id: int, *, expire_at: datetime
    ) -> None:
        await self.session.execute(
            update(RecurringPayment)
            .where(RecurringPayment.subscription_id == subscription_id)
            .values(
                pending_transaction_id=transaction_id,
                leased_until=None,
                submitted_at=None,
                pending_since=datetime_now(),
                cycle_expire_at=expire_at,
            )
        )

    async def release_pending(
        self,
        subscription_id: int,
        transaction_id: int,
        *,
        reason: Optional[str],
        retry_minutes: int = 5,
    ) -> None:
        order = await self.session.get(
            Transaction, transaction_id, with_for_update=True, populate_existing=True
        )
        if order is None or order.status not in {
            TransactionStatus.FAILED,
            TransactionStatus.CANCELED,
        }:
            return
        row = await self.session.get(
            RecurringPayment, subscription_id, with_for_update=True, populate_existing=True
        )
        if row is None or row.pending_transaction_id != transaction_id:
            return
        if reason is not None:
            await self._notice_pause(
                subscription_id, reason, datetime_now() + timedelta(minutes=retry_minutes)
            )
        row.pending_transaction_id = None
        row.pending_since = None
        row.submitted_at = None
        row.last_error = RecurringReason.CUSTOMER_DISABLED if row.customer_disabled else reason
        row.leased_until = None
        row.next_attempt_at = (
            datetime_now() + timedelta(minutes=retry_minutes) if reason else datetime_now()
        )
        if reason is None:
            self._reset_cycle(row, datetime_now())
        await self.session.flush()

    async def fail_pending(
        self,
        subscription_id: int,
        reason: str,
        *,
        transaction_id: Optional[int] = None,
        permanent: bool = False,
    ) -> None:
        current = await self.get(subscription_id)
        expected = transaction_id or (current.pending_transaction_id if current else None)
        if expected is None:
            return
        # Match fulfillment's lock order and never let an old response detach a new attempt.
        order = await self.session.get(
            Transaction, expected, with_for_update=True, populate_existing=True
        )
        if order is None or order.status not in {
            TransactionStatus.CANCELED,
            TransactionStatus.FAILED,
        }:
            return
        row = await self.session.get(
            RecurringPayment, subscription_id, with_for_update=True, populate_existing=True
        )
        if row is None or row.pending_transaction_id != expected:
            return
        subscription = await self.session.get(Subscription, subscription_id)
        terms = await self.consent_terms(row.consent_id)
        now = datetime_now()
        row.pending_transaction_id = None
        row.pending_since = None
        row.submitted_at = None
        if await self._failure_while_closed(row, reason, permanent, now):
            return
        if (
            subscription is not None
            and row.cycle_expire_at is not None
            and subscription.expire_at > row.cycle_expire_at
        ):
            self._reset_cycle(row, now)
            return
        row.first_failure_at = row.first_failure_at if permanent else row.first_failure_at or now
        next_at = None if permanent else self._next_retry(row, terms, subscription, now)
        retry = bool(
            next_at is not None
            and not permanent
            and terms
            and row.enabled
            and not row.customer_disabled
        )
        row.retry_count += 0 if permanent else 1
        row.last_error = reason
        row.leased_until = None
        row.next_attempt_at = next_at if retry and next_at is not None else now
        row.bank_retry_at = next_at if retry else None
        if subscription is not None and retry:
            await persist_recurring_event(
                self.session,
                RecurringPaymentFailedEvent(
                    user_id=subscription.user_id,
                    subscription_id=subscription_id,
                    order_id=order.id,
                    amount=str(order.final_price),
                    currency=order.currency,
                    reason=reason,
                    next_attempt_at=next_at.isoformat() if retry and next_at is not None else None,
                    attempt=row.retry_count,
                ),
            )
        if not retry:
            row.last_error = reason if permanent else "retries_exhausted"
            if permanent:
                await self._reject_method(row, reason, now)
            if subscription is not None:
                await persist_recurring_event(
                    self.session,
                    RecurringPaymentExhaustedEvent(
                        user_id=subscription.user_id,
                        subscription_id=subscription_id,
                        order_id=order.id,
                        reason=row.last_error,
                    ),
                )
        await self.session.flush()

    async def _failure_while_closed(
        self,
        row: RecurringPayment,
        reason: str,
        permanent: bool,
        now: datetime,
    ) -> bool:
        if row.enabled and not row.customer_disabled:
            return False
        if permanent:
            await self._reject_method(row, reason, now)
        if row.customer_disabled:
            row.last_error = RecurringReason.CUSTOMER_DISABLED
        row.leased_until = None
        await self.session.flush()
        return True

    async def _reject_method(self, row: RecurringPayment, reason: str, now: datetime) -> None:
        row.enabled = False
        if not row.customer_disabled:
            row.disabled_at = now
        row.payment_method_id = None
        if reason == RecurringReason.PERMISSION_REVOKED and row.consent_id is not None:
            await self.session.execute(
                update(RecurringConsent)
                .where(RecurringConsent.id == row.consent_id, RecurringConsent.revoked_at.is_(None))
                .values(revoked_at=now, revoked_channel="provider")
            )

    @staticmethod
    def _next_retry(
        row: RecurringPayment,
        terms: Optional[RecurringTerms],
        subscription: Optional[Subscription],
        now: datetime,
    ) -> Optional[datetime]:
        if terms is None or row.first_failure_at is None:
            return None
        offsets = terms.retry_offsets_hours
        count = row.retry_count
        if count < 0 or count >= len(offsets):
            return None
        # Missed slots are skipped after an outage; never catch up by hammering the bank.
        next_at = next(
            (
                row.first_failure_at + timedelta(hours=hour)
                for hour in offsets
                if row.first_failure_at + timedelta(hours=hour) > now
            ),
            None,
        )
        if next_at is None:
            return None
        if subscription and next_at > subscription.expire_at + timedelta(
            hours=terms.max_overdue_hours
        ):
            return None
        return next_at

    @staticmethod
    def _reset_cycle(row: RecurringPayment, now: datetime) -> None:
        row.bank_retry_at = None
        row.first_failure_at = None
        row.retry_count = 0
        row.cycle_expire_at = None
        row.pending_since = None
        row.submitted_at = None
        row.last_error = "customer_disabled" if row.customer_disabled else None
        row.leased_until = None
        row.next_attempt_at = now

    async def retire_pending(
        self,
        subscription_id: int,
        transaction_id: Optional[int] = None,
        *,
        force_unknown: bool = False,
        notify: bool = True,
    ) -> bool:
        if transaction_id is None:
            current = await self.get(subscription_id)
            if current is None or current.pending_transaction_id is None:
                return False
            transaction_id = current.pending_transaction_id
        return await self._retire_pending_order(
            subscription_id, transaction_id, force_unknown=force_unknown, notify=notify
        )

    async def _retire_pending_order(
        self, subscription_id: int, transaction_id: int, *, force_unknown: bool, notify: bool
    ) -> bool:
        order = await self.session.get(
            Transaction, transaction_id, with_for_update=True, populate_existing=True
        )
        if (
            order is None
            or not order.is_recurring
            or order.target_subscription_id != subscription_id
            or order.status
            not in {
                TransactionStatus.PENDING,
                TransactionStatus.FAILED,
                TransactionStatus.CANCELED,
            }
            or (order.external_payment_id is not None and not force_unknown)
        ):
            return False
        row = await self.session.get(
            RecurringPayment, subscription_id, with_for_update=True, populate_existing=True
        )
        if row is None or row.pending_transaction_id != transaction_id:
            return False
        now = datetime_now()
        if (
            not force_unknown
            and order.status is TransactionStatus.PENDING
            and order.created_at > now - SAFE_REPOST_WINDOW
        ):
            return False
        unknown = row.submitted_at is not None or order.external_payment_id is not None
        order.status = TransactionStatus.FAILED if unknown else TransactionStatus.CANCELED
        reconnected = unknown and await self.has_manual_after(
            subscription_id, created_at=order.created_at, plan_id=order.plan_id
        )
        if unknown and not reconnected and not row.customer_disabled and notify:
            await self._notice_pause(subscription_id, RecurringReason.PAYMENT_STATUS_UNKNOWN)
        row.pending_transaction_id = None
        row.pending_since = None
        row.leased_until = None
        row.next_attempt_at = now
        if row.customer_disabled:
            row.last_error = RecurringReason.CUSTOMER_DISABLED
        elif unknown and not reconnected:
            row.enabled = False
            row.disabled_at = now
            row.last_error = RecurringReason.PAYMENT_STATUS_UNKNOWN
        elif not unknown or (reconnected and not force_unknown):
            # A delivered manual renewal already paid this cycle; its future mandate
            # must not inherit a retired attempt's submission marker.
            self._reset_cycle(row, now)
        await self.session.flush()
        logger.warning(
            f"Retired recurring order '{transaction_id}'; provider outcome unknown: {unknown}"
        )
        return True

    async def cancel_unsent(self, subscription_id: int, transaction_id: int) -> bool:
        order = await self.session.get(
            Transaction, transaction_id, with_for_update=True, populate_existing=True
        )
        row = await self.session.get(
            RecurringPayment, subscription_id, with_for_update=True, populate_existing=True
        )
        if (
            order is None
            or row is None
            or row.pending_transaction_id != transaction_id
            or order.status is not TransactionStatus.PENDING
            or order.external_payment_id is not None
            or row.submitted_at is not None
        ):
            return False
        order.status = TransactionStatus.CANCELED
        row.pending_transaction_id = None
        row.pending_since = None
        row.leased_until = None
        await self.session.flush()
        return True

    async def clear_submission(self, subscription_id: int) -> None:
        await self.session.execute(
            update(RecurringPayment)
            .where(RecurringPayment.subscription_id == subscription_id)
            .values(submitted_at=None)
        )

    async def mark_submitted(self, subscription_id: int) -> datetime:
        token = await self.session.scalar(
            update(RecurringPayment)
            .where(RecurringPayment.subscription_id == subscription_id)
            .values(
                submitted_at=func.greatest(
                    datetime_now(), RecurringPayment.submitted_at + timedelta(microseconds=1)
                )
            )
            .returning(RecurringPayment.submitted_at)
        )
        if token is None:
            raise RuntimeError("Recurring mandate disappeared before submission")
        return token

    async def has_manual_waiting(self, subscription_id: int) -> bool:
        return (
            await self.session.scalar(
                select(Transaction.id)
                .where(
                    Transaction.target_subscription_id == subscription_id,
                    Transaction.is_recurring.is_(False),
                    Transaction.status == TransactionStatus.PAID,
                    Transaction.fulfilled_at.is_(None),
                    Transaction.is_test.is_(False),
                )
                .limit(1)
            )
            is not None
        )

    async def has_manual_after(
        self, subscription_id: int, *, created_at: Optional[datetime], plan_id: Optional[int]
    ) -> bool:
        if created_at is None:
            return True
        return (
            await self.session.scalar(
                select(Transaction.id)
                .where(
                    Transaction.fulfilled_subscription_id == subscription_id,
                    Transaction.is_recurring.is_(False),
                    Transaction.status == TransactionStatus.PAID,
                    Transaction.fulfilled_at >= created_at,
                    Transaction.plan_id == plan_id,
                )
                .limit(1)
            )
            is not None
        )

    async def _latest_order(self, subscription_id: int) -> Optional[int]:
        latest: Optional[int] = await self.session.scalar(
            select(Transaction.id)
            .where(
                Transaction.target_subscription_id == subscription_id,
                Transaction.is_recurring.is_(True),
                Transaction.is_test.is_(False),
            )
            .order_by(Transaction.id.desc())
            .limit(1)
        )
        return latest

    async def on_canceled(self, order_id: int, reason: str) -> None:
        order = await self.session.get(
            Transaction, order_id, with_for_update=True, populate_existing=True
        )
        if (
            order is None
            or not order.is_recurring
            or order.status is not TransactionStatus.CANCELED
            or order.target_subscription_id is None
        ):
            return
        row = await self.session.get(
            RecurringPayment,
            order.target_subscription_id,
            with_for_update=True,
            populate_existing=True,
        )
        if row is None:
            return
        resolved = recurring_reason(reason) or RecurringReason.BANK_DECLINED
        if row.pending_transaction_id != order.id:
            if (
                row.pending_transaction_id is not None
                or row.submitted_at is None
                or await self._latest_order(row.subscription_id) != order.id
            ):
                return
            active = (
                not row.customer_disabled
                and row.consent_id == order.recurring_consent_id
                and row.payment_method_id is not None
                and await self.consent_terms(row.consent_id) is not None
            )
            if not active:
                previous = row.last_error
                now = datetime_now()
                self._reset_cycle(row, now)
                if resolved.policy.terminal:
                    await self._reject_method(row, resolved, now)
                if previous == RecurringReason.ADMIN_CLOSED and not row.customer_disabled:
                    row.last_error = previous
                await self.session.flush()
                return
            row.pending_transaction_id = order.id
            row.enabled = True
            await self.session.flush()
        await self.fail_pending(
            row.subscription_id,
            resolved,
            transaction_id=order.id,
            permanent=resolved.policy.terminal,
        )

    async def _on_recurring_fulfilled(
        self, order: Transaction, subscription_id: int, now: datetime
    ) -> None:
        row = await self.session.get(
            RecurringPayment, subscription_id, with_for_update=True, populate_existing=True
        )
        if row is None:
            return
        if row.pending_transaction_id != order.id:
            latest = await self._latest_order(subscription_id)
            if (
                row.pending_transaction_id is not None
                or row.submitted_at is None
                or latest != order.id
            ):
                return
            recovered = (
                not row.customer_disabled
                and row.consent_id == order.recurring_consent_id
                and row.payment_method_id is not None
                and await self.consent_terms(row.consent_id) is not None
            )
            if recovered:
                row.enabled = True
                row.disabled_at = None
        row.pending_transaction_id = None
        self._reset_cycle(row, now)
        await self.session.flush()

    async def on_fulfilled(self, order: Transaction, subscription_id: int) -> None:
        now = datetime_now()
        if order.is_recurring:
            await self._on_recurring_fulfilled(order, subscription_id, now)
            return
        await self.retire_pending(subscription_id)
        previous = (
            await self.get(order.target_subscription_id)
            if order.target_subscription_id is not None
            and order.target_subscription_id != subscription_id
            else None
        )
        if previous is not None and previous.customer_disabled:
            await self.set_enabled(subscription_id, False, disabled_at=previous.disabled_at)
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
            self._preserve_manual_renewal(row, now)
            return
        if order.status is not TransactionStatus.PAID or order.is_test:
            return
        if (
            not order.saved_payment_method_id
            and row.payment_method_id
            and not row.customer_disabled
            and await self.consent_terms(row.consent_id) is not None
        ):
            self._preserve_manual_renewal(row, now)
            return
        await self._adopt_consent(row, order, subscription_id, now)

    @staticmethod
    def _preserve_manual_renewal(row: RecurringPayment, now: datetime) -> None:
        row.leased_until = None
        row.bank_retry_at = None
        if row.source_transaction_id is None or row.consent_id is None:
            return
        row.first_failure_at = None
        row.retry_count = 0
        row.last_error = (
            RecurringReason.CUSTOMER_DISABLED
            if row.customer_disabled
            else RecurringReason.PAYMENT_STATUS_UNKNOWN
            if row.submitted_at and row.pending_transaction_id is None
            else None
        )
        row.next_attempt_at = now
        if row.pending_transaction_id is None:
            row.cycle_expire_at = None

    async def _adopt_consent(
        self, row: RecurringPayment, order: Transaction, subscription_id: int, now: datetime
    ) -> None:
        consent = (
            await self.session.get(RecurringConsent, order.recurring_consent_id)
            if order.recurring_consent_id is not None
            else None
        )
        valid = bool(
            consent and consent.revoked_at is None and consent.owner_user_id == order.user_id
        )
        # A late paid order must not undo a withdrawal made after its confirmation.
        opted_out = row.customer_disabled and not (
            valid
            and consent is not None
            and row.disabled_at is not None
            and consent.accepted_at > row.disabled_at
        )
        if not order.saved_payment_method_id and valid and not opted_out:
            await self._notice_pause(subscription_id, RecurringReason.PAYMENT_METHOD_NOT_SAVED)
        if row.consent_id is not None and row.consent_id != order.recurring_consent_id:
            await self.session.execute(
                update(RecurringConsent)
                .where(RecurringConsent.id == row.consent_id, RecurringConsent.revoked_at.is_(None))
                .values(revoked_at=now, revoked_channel="replaced")
            )
        row.source_transaction_id = order.id
        row.payment_method_id = order.saved_payment_method_id
        row.shop_id = order.payment_method_shop_id or ""
        row.consent_id = consent.id if valid and consent is not None and not opted_out else None
        row.customer_disabled = opted_out
        if consent is not None and valid:
            consent.subscription_id = subscription_id
        row.enabled = bool(row.payment_method_id) and valid and not opted_out
        if row.enabled:
            row.disabled_at = None
        row.last_error = (
            "customer_disabled"
            if opted_out
            else None
            if row.enabled
            else "consent_required"
            if not valid
            else "payment_method_not_saved"
        )
        row.leased_until = None
        row.next_attempt_at = now
        row.bank_retry_at = None
        row.first_failure_at = None
        row.retry_count = 0
        if row.pending_transaction_id is None:
            row.cycle_expire_at = None
            row.submitted_at = None
        await self.session.flush()
