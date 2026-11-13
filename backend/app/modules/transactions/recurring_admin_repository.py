from sqlalchemy import String, case, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.constants import ZERO_AMOUNT
from app.core.db.models import RecurringPayment, Subscription, Transaction, User
from app.core.enums import Currency, Role, TransactionStatus
from app.modules.transactions.recurring_admin import (
    ListRecurringPaymentsDto,
    RecurringPaymentAdminItem,
    RecurringPaymentAdminSummary,
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
        attention = RecurringPayment.last_error.is_not(None) & ~RecurringPayment.customer_disabled
        retrying = RecurringPayment.first_failure_at.is_not(None) & RecurringPayment.enabled
        hard_attention = RecurringPayment.last_error.in_(
            {
                "payment_status_unknown",
                "pending_timeout",
                "retries_exhausted",
                "price_changed",
                "subscription_changed",
                "shop_changed",
                "consent_required",
                "plan_unavailable",
                "customer_email_required",
                "gateway_disabled",
                "merchant_unavailable",
                "subscription_unavailable",
                "permission_revoked",
                "payment_method_restricted",
                "card_expired",
                "fraud_suspected",
            }
        )
        state = case(
            (hard_attention & ~RecurringPayment.customer_disabled, "attention"),
            (RecurringPayment.pending_transaction_id.is_not(None), "pending"),
            (retrying, "retrying"),
            (attention, "attention"),
            (RecurringPayment.enabled, "enabled"),
            else_="disabled",
        )
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
                RecurringPayment.attempted_at,
                RecurringPayment.pending_transaction_id,
                RecurringPayment.retry_count,
                RecurringPayment.first_failure_at,
                source.base_price.label("amount_limit"),
                source.currency,
                Subscription.expire_at,
            )
            .join(Subscription, Subscription.id == RecurringPayment.subscription_id)
            .join(User, User.id == Subscription.user_id)
            .outerjoin(source, source.id == RecurringPayment.source_transaction_id)
        )
        predicates = {
            "enabled": RecurringPayment.enabled,
            "disabled": ~RecurringPayment.enabled,
            "pending": RecurringPayment.pending_transaction_id.is_not(None),
            "retrying": retrying,
            "attention": attention,
        }
        if data.state is not None:
            stmt = stmt.where(predicates[data.state])
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
            if values["last_error"] in {
                "pending_timeout",
                "payment_status_unknown",
                "retries_exhausted",
                "price_changed",
                "subscription_changed",
                "shop_changed",
                "consent_required",
                "plan_unavailable",
                "customer_email_required",
                "subscription_unavailable",
                "permission_revoked",
                "payment_method_restricted",
                "card_expired",
                "fraud_suspected",
            }:
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
                        func.count().filter(RecurringPayment.enabled).label("enabled"),
                        func.count().filter(~RecurringPayment.enabled).label("disabled"),
                        func.count()
                        .filter(RecurringPayment.pending_transaction_id.is_not(None))
                        .label("pending"),
                        func.count()
                        .filter(
                            RecurringPayment.first_failure_at.is_not(None)
                            & RecurringPayment.enabled
                        )
                        .label("retrying"),
                        func.count()
                        .filter(
                            RecurringPayment.last_error.is_not(None)
                            & ~RecurringPayment.customer_disabled
                        )
                        .label("attention"),
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
