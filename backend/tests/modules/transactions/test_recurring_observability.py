from dataclasses import fields
from datetime import timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select, update

from app.core.db.models import EventOutboxEntry, RecurringPayment, User
from app.core.enums import Currency, Locale, Role, TransactionStatus
from app.core.event_bus import EventBus
from app.core.events import EventCategory
from app.core.exceptions import ValidationError
from app.core.utils.time import datetime_now
from app.modules.customer_notifications.render_args import customer_render_args
from app.modules.customer_notifications.routing import CustomerChannel, channels_for
from app.modules.customer_notifications.subscribers import register_subscribers
from app.modules.notifications.render import NotificationRenderer
from app.modules.transactions.dto import CreateTransactionDto
from app.modules.transactions.recurring_admin import ListRecurringPaymentsDto
from app.modules.transactions.recurring_admin_repository import RecurringPaymentAdminRepository
from app.modules.transactions.recurring_dto import SetRecurringPaymentDto
from app.modules.transactions.recurring_events import (
    RecurringPaymentExhaustedEvent,
    RecurringPaymentFailedEvent,
    RecurringPaymentPausedEvent,
    RecurringPaymentUpcomingEvent,
    persist_recurring_event,
)
from tests.fakes.events import stored_event
from tests.modules.transactions import test_recurring_payments
from tests.seeded_translations import seeded_fluent_source

case = test_recurring_payments.case


async def _order(case, transaction_repository, uow, status):
    values = {
        field.name: getattr(case.source, field.name) for field in fields(CreateTransactionDto)
    }
    values.update(
        is_recurring=True, target_subscription_id=case.subscription.id, idempotency_key=uuid4().hex
    )
    async with uow:
        order = await transaction_repository.create(CreateTransactionDto(**values))
        await transaction_repository.mark_status(order.id, status)
    return order


async def test_admin_summary_counts_only_real_recurring_orders(
    case, session, uow, transaction_repository
):
    await _order(case, transaction_repository, uow, TransactionStatus.PAID)
    await _order(case, transaction_repository, uow, TransactionStatus.CANCELED)
    repository = RecurringPaymentAdminRepository(session)
    summary = await repository.summary()
    assert summary.total == 1 and summary.enabled == 1
    assert summary.paid_renewals == 1 and summary.failed_renewals == 1
    assert summary.revenue == Decimal("400") and summary.currency == "RUB"
    items, total = await repository.list_page(
        ListRecurringPaymentsDto(), actor_id=0, show_staff=True
    )
    assert total == 1 and items[0].subscription_id == case.subscription.id
    assert items[0].amount_limit == Decimal("500")
    assert "method-token" not in items[0].model_dump_json()
    assert "payment_method_id" not in items[0].model_dump_json()


async def test_admin_sees_stopped_pending_payments_as_attention(
    case, session, uow, transaction_repository
):
    order = await _order(case, transaction_repository, uow, TransactionStatus.PENDING)
    async with uow:
        await session.execute(
            update(RecurringPayment)
            .where(RecurringPayment.subscription_id == case.subscription.id)
            .values(enabled=False, pending_transaction_id=order.id, last_error="pending_timeout")
        )
    repository = RecurringPaymentAdminRepository(session)
    items, total = await repository.list_page(
        ListRecurringPaymentsDto(state="attention"), actor_id=0, show_staff=True
    )
    assert total == 1 and items[0].state == "attention"
    assert items[0].pending_transaction_id == order.id and items[0].next_attempt_at is None
    summary = await repository.summary()
    assert summary.pending == 1 and summary.attention == 1


async def test_admin_can_filter_retries_without_exposing_staff_names(case, session, uow):
    async with uow:
        await session.execute(update(User).where(User.id == case.user.id).values(role=Role.ADMIN))
        await session.execute(
            update(RecurringPayment)
            .where(RecurringPayment.subscription_id == case.subscription.id)
            .values(
                retry_count=2,
                first_failure_at=datetime_now() - timedelta(hours=3),
                last_error="insufficient_funds",
            )
        )
    repository = RecurringPaymentAdminRepository(session)
    items, total = await repository.list_page(
        ListRecurringPaymentsDto(state="retrying"), actor_id=0, show_staff=False
    )
    assert total == 1 and items[0].state == "retrying" and items[0].retry_count == 2
    assert items[0].user_name is None
    _, total = await repository.list_page(
        ListRecurringPaymentsDto(search=case.user.name), actor_id=0, show_staff=False
    )
    assert total == 0


async def test_repository_notice_is_committed_with_its_state_and_rolls_back_together(session, uow):
    with pytest.raises(RuntimeError):
        async with uow:
            await persist_recurring_event(
                session,
                RecurringPaymentPausedEvent(
                    user_id=5, subscription_id=7, reason="provider_unavailable"
                ),
            )
            assert (
                await session.scalar(
                    select(EventOutboxEntry).where(
                        EventOutboxEntry.event_type == "RecurringPaymentPausedEvent"
                    )
                )
                is not None
            )
            raise RuntimeError("rollback")
    assert (
        await session.scalar(
            select(EventOutboxEntry).where(
                EventOutboxEntry.event_type == "RecurringPaymentPausedEvent"
            )
        )
        is None
    )


_EVENTS = [
    RecurringPaymentUpcomingEvent(
        user_id=5,
        subscription_id=7,
        amount="500",
        currency=Currency.RUB,
        scheduled_at="2026-11-15T12:00:00+00:00",
    ),
    RecurringPaymentFailedEvent(
        user_id=5,
        subscription_id=7,
        order_id=8,
        amount="500",
        currency=Currency.RUB,
        reason="insufficient_funds",
        next_attempt_at="2026-11-15T13:00:00+00:00",
        attempt=1,
    ),
    RecurringPaymentPausedEvent(user_id=5, subscription_id=7, reason="merchant_unavailable"),
    RecurringPaymentExhaustedEvent(user_id=5, subscription_id=7, reason="retries_exhausted"),
]


@pytest.mark.parametrize("event", _EVENTS)
@pytest.mark.parametrize("locale", [Locale.RU, Locale.EN])
async def test_recurring_events_reach_customer_channels_and_have_complete_templates(event, locale):
    bus = EventBus()
    register_subscribers(bus)
    with patch(
        "app.modules.customer_notifications.tasks.notify_customer_task.kiq", new_callable=AsyncMock
    ) as dispatched:
        await bus.dispatch_stored(stored_event(event))
    dispatched.assert_awaited_once()
    fields = dispatched.await_args.kwargs
    assert fields["user_id"] == 5 and fields["subscription_id"] == 7
    assert channels_for(event.event_type, telegram_id=1, email="customer@example.com") == [
        CustomerChannel.TELEGRAM,
        CustomerChannel.EMAIL,
    ]
    renderer = NotificationRenderer({locale: seeded_fluent_source(locale)}, default_locale=locale)
    title, body = renderer.render(
        locale, "Customer" + event.event_type, customer_render_args(fields["args"], locale)
    )
    assert title and body and "{" not in body
    assert event.category is EventCategory.PAYMENT
    if isinstance(event, RecurringPaymentUpcomingEvent):
        assert "15.11.2026 12:00 UTC" in body
    if isinstance(event, RecurringPaymentFailedEvent):
        assert "15.11.2026 13:00 UTC" in body


async def test_customer_state_distinguishes_a_pause_from_withdrawing_consent(case, uow):
    async with uow:
        await case.repository.pause(case.subscription.id, "price_changed")
    state = await case.get_state(case.user, case.subscription.id)
    assert state.enabled and state.paused and not state.available
    assert not state.retrying and state.next_payment_at is None
    assert not state.customer_disabled


async def test_customer_state_uses_the_actual_scheduled_retry(case, session, uow):
    scheduled = datetime_now() + timedelta(hours=3)
    async with uow:
        await session.execute(
            update(RecurringPayment)
            .where(RecurringPayment.subscription_id == case.subscription.id)
            .values(
                first_failure_at=datetime_now(),
                retry_count=1,
                last_error="insufficient_funds",
                next_attempt_at=scheduled,
            )
        )
    state = await case.get_state(case.user, case.subscription.id)
    assert state.enabled and state.available and state.retrying and not state.paused
    assert state.next_retry_at == state.next_payment_at == scheduled


async def test_customer_state_keeps_the_accepted_lead_time_after_configuration_changes(case):
    before = await case.get_state(case.user, case.subscription.id)
    case.worker._config.recurring.lead_minutes += 60
    after = await case.get_state(case.user, case.subscription.id)
    assert after.next_payment_at == before.next_payment_at
    assert after.accepted_terms.lead_minutes != case.worker._config.recurring.lead_minutes


@pytest.mark.parametrize(
    "reason", ["payment_status_unknown", "pending_timeout", "permission_revoked"]
)
async def test_customer_cannot_restart_an_unsafe_payment_from_the_card(case, session, uow, reason):
    async with uow:
        await session.execute(
            update(RecurringPayment)
            .where(RecurringPayment.subscription_id == case.subscription.id)
            .values(last_error=reason, enabled=True)
        )
    state = await case.get_state(case.user, case.subscription.id)
    assert state.enabled and state.paused and not state.available
    assert state.next_retry_at is None and state.next_payment_at is None
    with pytest.raises(ValidationError):
        await case.set_state(
            case.user, SetRecurringPaymentDto(subscription_id=case.subscription.id, enabled=True)
        )
