from sqlalchemy import String, and_, case, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.constants import ZERO_AMOUNT
from app.core.db.models import RecurringConsent, RecurringPayment, Subscription, Transaction, User
from app.core.enums import Currency, Role, TransactionStatus
from app.core.utils.time import datetime_now
from app.modules.transactions.recurring_admin import (
    ListRecurringPaymentsDto,
    RecurringPaymentAdminItem,
    RecurringPaymentAdminSummary,
)
from app.modules.transactions.recurring_policy import (
    RecurringReason,
    RecurringState,
    RetryKind,
    recurring_reason,
)
from app.modules.transactions.recurring_queries import (
    recurring_state_expression,
    renewal_window_expired,
)


class RecurringPaymentAdminRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_page(
        self,
        data: ListRecurringPaymentsDto,
        *,
        actor_id: int,
        show_staff: bool,
    ) -> tuple[list[RecurringPaymentAdminItem], int]:
        source = aliased(Transaction)
        pending = aliased(Transaction)
        state = recurring_state_expression()
        shown_name = (
            User.name
            if show_staff
            else case(
                (
                    (User.role.in_([Role.ADMIN, Role.OWNER, Role.SYSTEM])) & (User.id != actor_id),
                    None,
                ),
                else_=User.name,
            )
        )
        stmt = (
            select(
                RecurringPayment.subscription_id,
                Subscription.user_id,
                shown_name.label("user_name"),
                func.coalesce(Subscription.plan_snapshot["name"].astext, "—").label("plan_name"),
                RecurringPayment.enabled,
                RecurringPayment.customer_disabled,
                state.label("state"),
                RecurringPayment.last_error,
                RecurringPayment.next_attempt_at,
                RecurringPayment.submitted_at,
                RecurringPayment.pending_transaction_id,
                pending.external_payment_id,
                pending.status.label("_pending_status"),
                RecurringPayment.payment_method_id.is_not(None).label("_has_method"),
                and_(
                    RecurringPayment.consent_id.is_not(None), RecurringConsent.revoked_at.is_(None)
                ).label("_authorized"),
                renewal_window_expired(datetime_now()).label("_expired"),
                RecurringPayment.retry_count,
                RecurringPayment.first_failure_at,
                source.base_price.label("amount_limit"),
                source.currency,
                Subscription.expire_at,
            )
            .join(Subscription, Subscription.id == RecurringPayment.subscription_id)
            .join(User, User.id == Subscription.user_id)
            .outerjoin(source, source.id == RecurringPayment.source_transaction_id)
            .outerjoin(pending, pending.id == RecurringPayment.pending_transaction_id)
            .outerjoin(RecurringConsent, RecurringConsent.id == RecurringPayment.consent_id)
        )
        if data.state is not None:
            stmt = stmt.where(state == data.state)
        if data.search:
            pattern = (
                "%"
                + data.search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                + "%"
            )
            stmt = stmt.where(
                or_(
                    shown_name.ilike(pattern, escape="\\"),
                    cast(RecurringPayment.subscription_id, String).ilike(pattern, escape="\\"),
                    cast(Subscription.user_id, String).ilike(pattern, escape="\\"),
                )
            )
        total = await self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = (
            await self.session.execute(
                stmt.order_by(
                    RecurringPayment.last_error.is_not(None).desc(),
                    RecurringPayment.next_attempt_at,
                    RecurringPayment.subscription_id,
                )
                .offset((data.page - 1) * data.page_size)
                .limit(data.page_size)
            )
        ).mappings()
        items = []
        for row in rows:
            values = dict(row)
            reason = recurring_reason(values["last_error"])
            pending_status = values.pop("_pending_status")
            has_method = values.pop("_has_method")
            authorized = values.pop("_authorized")
            expired = values.pop("_expired")
            values["can_check"] = bool(values["external_payment_id"])
            values["can_close"] = pending_status is TransactionStatus.PENDING
            values["can_retry"] = bool(
                not values["customer_disabled"]
                and values["pending_transaction_id"] is None
                and values["submitted_at"] is None
                and has_method
                and authorized
                and not expired
                and reason
                and (
                    reason.policy.retry is RetryKind.TECHNICAL
                    or reason is RecurringReason.PROVIDER_CONFIGURATION_ERROR
                )
            )
            if values["pending_transaction_id"] is None and (
                values["customer_disabled"] or reason and reason.policy.retry is RetryKind.NONE
            ):
                values["next_attempt_at"] = None
            currency = values["currency"]
            values["currency"] = currency.value if currency is not None else None
            items.append(RecurringPaymentAdminItem.model_validate(values))
        return items, total

    async def summary(self) -> RecurringPaymentAdminSummary:
        mandate = (
            (
                await self.session.execute(
                    select(
                        func.count().label("total"),
                        *(
                            func.count()
                            .filter(recurring_state_expression() == state.value)
                            .label(state.value)
                            for state in RecurringState
                        ),
                    ).select_from(RecurringPayment)
                )
            )
            .mappings()
            .one()
        )
        money = (
            (
                await self.session.execute(
                    select(
                        func.count()
                        .filter(Transaction.status == TransactionStatus.PAID)
                        .label("paid_renewals"),
                        func.count()
                        .filter(
                            Transaction.status.in_(
                                [TransactionStatus.FAILED, TransactionStatus.CANCELED]
                            )
                        )
                        .label("failed_renewals"),
                        func.sum(Transaction.final_price)
                        .filter(Transaction.status == TransactionStatus.PAID)
                        .label("revenue"),
                    ).where(
                        Transaction.is_recurring,
                        ~Transaction.is_test,
                        Transaction.currency == Currency.RUB,
                    )
                )
            )
            .mappings()
            .one()
        )
        return RecurringPaymentAdminSummary(
            **dict(mandate), **{**dict(money), "revenue": money["revenue"] or ZERO_AMOUNT}
        )
