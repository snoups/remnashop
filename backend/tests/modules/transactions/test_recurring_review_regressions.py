import asyncio
import json
from dataclasses import fields, replace
from datetime import timedelta
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import select, update

import app.modules.transactions.usecases.process_recurring_payments as worker_module
from app.core.db.models import (
    EventOutboxEntry,
    RecurringConsent,
    RecurringPayment,
    Subscription,
    Transaction,
)
from app.core.enums import (
    Currency,
    PaymentGatewayType,
    PlanType,
    PurchaseChannel,
    PurchaseType,
    SubscriptionStatus,
    TransactionStatus,
)
from app.core.utils.time import datetime_now
from app.modules.plans.dto import (
    CreatePlanDto,
    SetPlanDurationDto,
    SetPlanDurationsDto,
    UpdatePlanDto,
    UpdatePlanSquadsDto,
)
from app.modules.subscriptions.dto import (
    ChangeSubscriptionPlanDto,
    CreateSubscriptionDto,
    PurchaseSubscriptionDto,
)
from app.modules.subscriptions.usecases.change_subscription_plan import (
    ChangeSubscriptionPlanUseCase,
)
from app.modules.transactions.dto import CreateTransactionDto, HandleWebhookDto, WebhookRequest
from app.modules.transactions.recurring_admin import ListRecurringPaymentsDto
from app.modules.transactions.recurring_admin_repository import RecurringPaymentAdminRepository
from app.modules.transactions.recurring_dto import SetRecurringPaymentDto
from app.modules.transactions.recurring_policy import RecurringState, classify
from app.modules.transactions.recurring_terms import build_recurring_terms
from app.modules.transactions.usecases import HandlePaymentWebhookUseCase
from tests.fakes.events import RecordingEventPublisher
from tests.fakes.remnawave import _user_payload
from tests.modules.transactions import test_recurring_payments as cases

case = cases.case


@pytest.fixture(autouse=True)
def production_session_mode(session):
    session.autoflush = False


async def _order(
    case,
    transaction_repository,
    uow,
    *,
    purchase_type=PurchaseType.RENEW,
    consent=True,
    saved=True,
    plan=None,
):
    snapshot = plan or case.source.plan_snapshot
    consent_id = None
    async with uow:
        if consent:
            consent_id = await case.repository.record_consent(
                build_recurring_terms(
                    config=case.worker._config,
                    user_id=case.user.id,
                    plan_id=snapshot.plan_id,
                    target_subscription_id=case.subscription.id,
                    purchase_type=purchase_type,
                    initial_amount=Decimal("500"),
                    amount_limit=Decimal("500"),
                    currency=Currency.RUB,
                    duration_days=30,
                    locale=case.user.language,
                ),
                channel=PurchaseChannel.BOT,
                telegram_id=case.user.telegram_id,
            )
        values = {
            field.name: getattr(case.source, field.name) for field in fields(CreateTransactionDto)
        }
        values.update(
            idempotency_key=uuid4().hex,
            purchase_type=purchase_type,
            target_subscription_id=case.subscription.id,
            plan_id=snapshot.plan_id,
            plan_snapshot=snapshot,
            recurring_consent=consent,
            recurring_consent_id=consent_id,
        )
        order = await transaction_repository.create(CreateTransactionDto(**values))
        await transaction_repository.mark_status(order.id, TransactionStatus.PAID)
        if saved:
            await transaction_repository.remember_payment_method(order.id, "new-method", "1000")
    return order


async def _new_subscription(case, subscription_repository, uow, snapshot):
    async with uow:
        return await subscription_repository.create(
            CreateSubscriptionDto(
                user_id=case.user.id,
                remnawave_user_id=case.subscription.remnawave_user_id + 1,
                status=SubscriptionStatus.ACTIVE,
                traffic_limit=100,
                device_limit=3,
                expire_at=datetime_now() + timedelta(days=30),
                url="https://example.test/changed",
                plan_snapshot=snapshot,
            )
        )


async def _notice_types(session):
    return list(
        await session.scalars(
            select(EventOutboxEntry.event_type).where(
                EventOutboxEntry.event_type.in_(
                    [
                        "RecurringPaymentFailedEvent",
                        "RecurringPaymentPausedEvent",
                        "RecurringPaymentExhaustedEvent",
                    ]
                )
            )
        )
    )


async def test_one_day_plan_does_not_charge_again_at_purchase(case, session, uow, plan_repository):
    snapshot = replace(case.source.plan_snapshot, duration_days=1)
    expiry = datetime_now() + timedelta(days=1)
    async with uow:
        await plan_repository.set_durations(
            SetPlanDurationsDto(
                plan_id=snapshot.plan_id,
                durations=[SetPlanDurationDto(days=1, order_index=0, base_price=Decimal("500"))],
            )
        )
        terms = build_recurring_terms(
            config=case.worker._config,
            user_id=case.user.id,
            plan_id=snapshot.plan_id,
            target_subscription_id=case.subscription.id,
            purchase_type=PurchaseType.RENEW,
            initial_amount=Decimal("500"),
            amount_limit=Decimal("500"),
            currency=Currency.RUB,
            duration_days=1,
            locale=case.user.language,
        )
        consent_id = await case.repository.record_consent(
            terms, channel=PurchaseChannel.BOT, telegram_id=case.user.telegram_id
        )
        await session.execute(
            update(Transaction)
            .where(Transaction.id == case.source.id)
            .values(duration_days=1, plan_snapshot=snapshot.to_json())
        )
        await session.execute(
            update(Subscription)
            .where(Subscription.id == case.subscription.id)
            .values(expire_at=expiry, plan_snapshot=snapshot.to_json())
        )
        await case.repository.set_enabled(case.subscription.id, True, consent_id=consent_id)
    await case.worker.system()
    mandate = await case.repository.get(case.subscription.id)
    assert terms.lead_minutes == 720
    assert "720" in terms.text
    assert not case.provider.posts
    assert mandate.next_attempt_at == expiry - timedelta(hours=12)
    state = await case.get_state(case.user, case.subscription.id)
    assert state.next_payment_at == mandate.next_attempt_at


async def test_unknown_payment_still_allows_withdrawal_and_late_success_cannot_reenable(
    case, session, uow, transaction_repository
):
    case.provider.lose_response = True
    await case.worker.system()
    mandate = await case.repository.get(case.subscription.id)
    async with uow:
        await session.execute(
            update(Transaction)
            .where(Transaction.id == mandate.pending_transaction_id)
            .values(created_at=datetime_now() - timedelta(hours=24))
        )
    await cases._tick_again(case, uow)
    parked = await case.get_state(case.user, case.subscription.id)
    assert not parked.enabled and parked.can_disable and parked.accepted_terms
    await case.set_state(
        case.user, SetRecurringPaymentDto(subscription_id=case.subscription.id, enabled=False)
    )
    async with uow:
        await transaction_repository.mark_status(
            mandate.pending_transaction_id, TransactionStatus.PAID
        )
        await transaction_repository.mark_fulfilled(
            mandate.pending_transaction_id, case.subscription.id
        )
    after = await case.repository.get(case.subscription.id)
    assert after.customer_disabled and not after.enabled
    assert after.last_error == "customer_disabled"


@pytest.mark.parametrize("withdraw_after_consent", [False, True])
async def test_plan_change_preserves_the_actual_withdrawal_time(
    case,
    transaction_repository,
    subscription_repository,
    session,
    uow,
    withdraw_after_consent,
    plan_repository,
):
    if not withdraw_after_consent:
        await case.set_state(
            case.user, SetRecurringPaymentDto(subscription_id=case.subscription.id, enabled=False)
        )
    async with uow:
        plan = await plan_repository.create(
            CreatePlanDto(
                name="Consent change",
                public_code="consent-change",
                type=PlanType.BOTH,
                traffic_limit=100,
                device_limit=3,
            )
        )
    snapshot = replace(case.source.plan_snapshot, plan_id=plan.id)
    order = await _order(
        case, transaction_repository, uow, purchase_type=PurchaseType.CHANGE, plan=snapshot
    )
    if withdraw_after_consent:
        await case.set_state(
            case.user, SetRecurringPaymentDto(subscription_id=case.subscription.id, enabled=False)
        )
    old = await case.repository.get(case.subscription.id)
    new = await _new_subscription(case, subscription_repository, uow, snapshot)
    async with uow:
        await case.repository.close_for_plan_change(case.subscription.id)
        await transaction_repository.mark_fulfilled(order.id, new.id)
    changed = await case.repository.get(new.id)
    assert changed.enabled is not withdraw_after_consent
    assert changed.customer_disabled is withdraw_after_consent
    if withdraw_after_consent:
        assert changed.disabled_at == old.disabled_at
    else:
        assert changed.payment_method_id == "new-method"
        assert changed.consent_id == order.recurring_consent_id


@pytest.mark.parametrize(
    ("consent", "saved", "disabled"),
    [
        (False, False, False),
        (False, False, True),
        (True, False, False),
        (True, True, False),
        (True, True, True),
    ],
)
async def test_manual_renewal_mandate_decision_table(
    case, transaction_repository, session, uow, consent, saved, disabled
):
    if disabled:
        await case.set_state(
            case.user, SetRecurringPaymentDto(subscription_id=case.subscription.id, enabled=False)
        )
    before = await case.repository.get(case.subscription.id)
    order = await _order(case, transaction_repository, uow, consent=consent, saved=saved)
    async with uow:
        await transaction_repository.mark_fulfilled(order.id, case.subscription.id)
    after = await case.repository.get(case.subscription.id)
    if consent and saved:
        assert after.enabled and after.payment_method_id == "new-method"
        assert after.consent_id == order.recurring_consent_id
    else:
        assert after.enabled == before.enabled
        assert after.payment_method_id == before.payment_method_id
        assert after.consent_id == before.consent_id
        assert after.customer_disabled == before.customer_disabled
    if consent and saved and before.consent_id:
        assert (await session.get(RecurringConsent, before.consent_id)).revoked_at is not None


@pytest.mark.parametrize("admin", [False, True])
async def test_real_plan_change_closes_old_mandate_before_order_fulfillment(
    case,
    admin,
    plan_repository,
    purchase_subscription_use_case,
    subscription_repository,
    user_repository,
    event_publisher,
    remnawave_store,
    uow,
    session,
):
    remnawave_store[case.subscription.remnawave_user_id] = _user_payload(
        user_id=case.subscription.remnawave_user_id,
        username="recurring-change",
        expire_at=case.subscription.expire_at,
    )
    async with uow:
        plan = await plan_repository.create(
            CreatePlanDto(
                name="Changed plan",
                public_code="changed-plan",
                type=PlanType.BOTH,
                traffic_limit=100,
                device_limit=3,
            )
        )
        plan = await plan_repository.set_durations(
            SetPlanDurationsDto(
                plan_id=plan.id,
                durations=[SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("500"))],
            )
        )
        await plan_repository.update_squads(
            UpdatePlanSquadsDto(plan_id=plan.id, internal_squads=[uuid4()], external_squad=None)
        )
        plan = await plan_repository.update(UpdatePlanDto(plan_id=plan.id, is_active=True))
    if admin:
        changed = await ChangeSubscriptionPlanUseCase(
            subscription_repository,
            user_repository,
            plan_repository,
            purchase_subscription_use_case,
            event_publisher,
            uow,
        ).system(
            ChangeSubscriptionPlanDto(
                subscription_id=case.subscription.id, plan_id=plan.id, duration_days=30
            )
        )
    else:
        changed = await purchase_subscription_use_case.system(
            PurchaseSubscriptionDto(
                user_id=case.user.id,
                plan_snapshot=replace(case.source.plan_snapshot, plan_id=plan.id),
                duration_days=30,
                price_paid=Decimal("500"),
                base_price=Decimal("500"),
                currency=Currency.RUB,
                purchase_type=PurchaseType.CHANGE,
                target_subscription_id=case.subscription.id,
            )
        )
    old = await case.repository.get(case.subscription.id)
    assert not old.enabled
    assert (await session.get(RecurringConsent, old.consent_id)).revoked_at is not None
    assert await case.repository.get(changed.id) is None
    before = len(case.provider.posts)
    await case.worker.system(case.subscription.id)
    assert len(case.provider.posts) == before


async def test_withdrawal_while_pending_survives_decline_and_can_be_reenabled(case, session, uow):
    case.provider.status = "pending"
    await case.worker.system()
    await case.set_state(
        case.user, SetRecurringPaymentDto(subscription_id=case.subscription.id, enabled=False)
    )
    case.provider.status = "canceled"
    case.provider.cancellation_reason = "insufficient_funds"
    await cases._tick_again(case, uow)
    state = await case.get_state(case.user, case.subscription.id)
    assert state.customer_disabled and state.available and state.last_error == "customer_disabled"
    assert not await _notice_types(session)
    enabled = await case.set_state(
        case.user,
        SetRecurringPaymentDto(
            subscription_id=case.subscription.id, enabled=True, terms_id=state.terms.terms_id
        ),
    )
    assert enabled.enabled
    assert len(case.provider.posts) == 1


@pytest.mark.parametrize("customer", [True, False])
async def test_unsent_reserved_payment_is_canceled_without_unknown_outcome(
    case, customer, gateway_repository, transaction_repository, session, uow
):
    await case.worker._reserve(await case.repository.get(case.subscription.id))
    reserved = await case.repository.get(case.subscription.id)
    if customer:
        await case.set_state(
            case.user, SetRecurringPaymentDto(subscription_id=case.subscription.id, enabled=False)
        )
    else:
        async with uow:
            await gateway_repository.update_settings(
                PaymentGatewayType.YOOKASSA, {"payment_mode": "single"}
            )
    await case.worker._charge_or_poll(case.subscription.id)
    current = await case.repository.get(case.subscription.id)
    assert current.pending_transaction_id is None and current.submitted_at is None
    assert (
        await transaction_repository.get_by_id(reserved.pending_transaction_id)
    ).status is TransactionStatus.CANCELED
    assert not case.provider.posts
    assert not await _notice_types(session)
    assert current.last_error != "payment_status_unknown"


async def test_canceled_worker_keeps_durable_possible_submission(case, monkeypatch):
    await case.worker._reserve(await case.repository.get(case.subscription.id))
    mandate, order, _ = await case.worker._pending_context(case.subscription.id)
    monkeypatch.setattr(
        worker_module, "submit_recurring", AsyncMock(side_effect=asyncio.CancelledError)
    )
    with pytest.raises(asyncio.CancelledError):
        await case.worker._submit_if_authorized(case.subscription.id, order)
    current = await case.repository.get(case.subscription.id)
    assert current.submitted_at is not None and current.pending_transaction_id == order.id


async def test_overdue_mandate_has_a_terminal_state_and_leaves_the_queue(case, session, uow):
    terms = await case.repository.consent_terms(
        (await case.repository.get(case.subscription.id)).consent_id
    )
    async with uow:
        await session.execute(
            update(Subscription)
            .where(Subscription.id == case.subscription.id)
            .values(expire_at=datetime_now() - timedelta(hours=terms.max_overdue_hours + 1))
        )
    now = datetime_now()
    assert case.subscription.id not in await case.repository.list_due(
        now, due_before=now + timedelta(days=2), limit=100
    )
    current = await case.repository.get(case.subscription.id)
    assert not current.enabled and current.last_error == "renewal_window_expired"
    notices = await _notice_types(session)
    assert notices == ["RecurringPaymentPausedEvent"]
    assert case.subscription.id not in await case.repository.list_due(
        now + timedelta(days=30), due_before=now + timedelta(days=31), limit=100
    )
    assert await _notice_types(session) == notices


async def test_pending_timeout_continues_hourly_poll_and_recovers_without_webhook(
    case, session, uow
):
    case.provider.status = "pending"
    await case.worker.system()
    initial = await case.repository.get(case.subscription.id)
    async with uow:
        await session.execute(
            update(RecurringPayment)
            .where(RecurringPayment.subscription_id == case.subscription.id)
            .values(pending_since=datetime_now() - timedelta(hours=25))
        )
    await cases._tick_again(case, uow)
    parked = await case.repository.get(case.subscription.id)
    assert parked.last_error == "pending_timeout"
    assert parked.pending_transaction_id == initial.pending_transaction_id
    assert parked.next_attempt_at > datetime_now() + timedelta(minutes=55)
    case.provider.status = "canceled"
    await cases._tick_again(case, uow)
    recovered = await case.repository.get(case.subscription.id)
    assert recovered.pending_transaction_id is None
    assert recovered.last_error == "bank_declined"
    assert len(case.provider.posts) == 1


async def test_poll_of_already_paid_order_does_not_touch_revenue_timestamp_or_redispatch(
    case, transaction_repository, uow
):
    await case.worker.system()
    current = await case.repository.get(case.subscription.id)
    paid = await transaction_repository.get_by_id(current.pending_transaction_id)
    count = len(case.dispatch.messages)
    async with uow:
        gateway = await case.worker._gateway()
    await case.worker._poll(case.subscription.id, paid, gateway)
    after = await transaction_repository.get_by_id(paid.id)
    assert after.updated_at == paid.updated_at
    assert len(case.dispatch.messages) == count


@pytest.mark.parametrize(
    ("body", "reason", "enabled"),
    [
        (
            {"type": "error", "code": "invalid_request", "parameter": "receipt.items"},
            "provider_configuration_error",
            True,
        ),
        (
            {
                "type": "error",
                "code": "invalid_request",
                "parameter": "payment_method_id",
                "description": "Payment method not found",
            },
            "payment_method_restricted",
            False,
        ),
        (
            {
                "type": "error",
                "code": "invalid_request",
                "parameter": "payment_method_id",
                "description": "Payment method is not available",
            },
            "merchant_unavailable",
            True,
        ),
    ],
)
async def test_http400_is_classified_without_bank_dunning(case, session, body, reason, enabled):
    case.provider.reject = True
    case.provider.reject_body = body
    await case.worker.system()
    current = await case.repository.get(case.subscription.id)
    assert current.last_error == reason and current.enabled is enabled
    assert current.bank_retry_at is None and current.first_failure_at is None
    assert len(await _notice_types(session)) == 1


async def test_first_enrollment_without_saved_method_is_reported(
    case, transaction_repository, session, uow
):
    async with uow:
        await session.execute(
            update(RecurringPayment)
            .where(RecurringPayment.subscription_id == case.subscription.id)
            .values(
                source_transaction_id=None, consent_id=None, payment_method_id=None, enabled=False
            )
        )
    order = await _order(case, transaction_repository, uow, consent=True, saved=False)
    async with uow:
        await transaction_repository.mark_fulfilled(order.id, case.subscription.id)
    current = await case.repository.get(case.subscription.id)
    assert not current.enabled and current.last_error == "payment_method_not_saved"
    assert current.consent_id == order.recurring_consent_id
    assert await _notice_types(session) == ["RecurringPaymentPausedEvent"]


@pytest.mark.parametrize(
    ("enabled", "customer_disabled", "pending", "failed", "reason"),
    [
        (True, False, False, False, None),
        (True, False, True, False, None),
        (True, False, False, True, "insufficient_funds"),
        (True, False, True, False, "pending_timeout"),
        (False, True, True, False, "customer_disabled"),
    ],
)
async def test_admin_filters_and_totals_use_the_same_state_as_customer_policy(
    case, session, uow, enabled, customer_disabled, pending, failed, reason
):
    async with uow:
        await session.execute(
            update(RecurringPayment)
            .where(RecurringPayment.subscription_id == case.subscription.id)
            .values(
                enabled=enabled,
                customer_disabled=customer_disabled,
                pending_transaction_id=case.source.id if pending else None,
                first_failure_at=datetime_now() if failed else None,
                last_error=reason,
            )
        )
    expected = classify(await case.repository.get(case.subscription.id))
    repository = RecurringPaymentAdminRepository(session)
    for state in RecurringState:
        rows, total = await repository.list_page(
            ListRecurringPaymentsDto(state=state), actor_id=0, show_staff=True
        )
        assert total == int(state is expected)
        assert all(row.state is expected for row in rows)
    totals = await repository.summary()
    assert sum(getattr(totals, state.value) for state in RecurringState) == totals.total == 1
    assert getattr(totals, expected.value) == 1


@pytest.mark.parametrize("withdrawn", [False, True])
@pytest.mark.parametrize("reason", ["insufficient_funds", "permission_revoked"])
async def test_late_cancel_webhook_resolves_lost_create_response_without_new_debit(
    case,
    session,
    uow,
    transaction_repository,
    gateway_repository,
    user_repository,
    withdrawn,
    reason,
):
    case.provider.lose_response = True
    await case.worker.system()
    pending = await case.repository.get(case.subscription.id)
    order = await transaction_repository.get_by_id(pending.pending_transaction_id)
    assert order.external_payment_id is None and pending.submitted_at is not None
    async with uow:
        await session.execute(
            update(Transaction)
            .where(Transaction.id == order.id)
            .values(created_at=datetime_now() - timedelta(hours=24))
        )
    await cases._tick_again(case, uow)
    retired = await case.repository.get(case.subscription.id)
    assert retired.pending_transaction_id is None and not retired.enabled
    if withdrawn:
        await case.set_state(
            case.user, SetRecurringPaymentDto(subscription_id=case.subscription.id, enabled=False)
        )
    notices_before = await _notice_types(session)
    payment_id = next(iter(case.provider.references))
    case.provider.status = "canceled"
    case.provider.cancellation_reason = reason
    handler = HandlePaymentWebhookUseCase(
        transaction_repository,
        gateway_repository,
        case.worker._factory,
        user_repository,
        RecordingEventPublisher(),
        uow,
        case.dispatch,
    )
    callback = HandleWebhookDto(
        gateway_type=PaymentGatewayType.YOOKASSA,
        request=WebhookRequest(
            body=json.dumps(
                {
                    "event": "payment.canceled",
                    "object": {
                        "id": payment_id,
                        "metadata": {"order_ref": order.idempotency_key},
                    },
                }
            ).encode(),
            headers={},
            client_ip="185.71.76.1",
        ),
    )
    await handler.system(callback)
    await handler.system(callback)
    after = await case.repository.get(case.subscription.id)
    canceled = await transaction_repository.get_by_id(order.id)
    assert (
        canceled.status is TransactionStatus.CANCELED and canceled.external_payment_id == payment_id
    )
    assert after.submitted_at is None and after.pending_transaction_id is None
    assert len(case.provider.posts) == 1 and not case.dispatch.messages
    if withdrawn:
        assert (
            after.customer_disabled
            and not after.enabled
            and after.last_error == "customer_disabled"
        )
        assert await _notice_types(session) == notices_before
    elif reason == "insufficient_funds":
        assert after.enabled and after.retry_count == 1 and after.last_error == reason
        assert await _notice_types(session) == notices_before + ["RecurringPaymentFailedEvent"]
    else:
        assert not after.enabled and after.payment_method_id is None and after.last_error == reason
    if reason == "permission_revoked":
        assert after.payment_method_id is None


async def test_manual_checkout_cannot_cancel_a_reserved_recurring_debit(
    case, transaction_repository, uow
):
    case.provider.status = "pending"
    await case.worker.system()
    before = await case.repository.get(case.subscription.id)
    async with uow:
        result = await transaction_repository.cancel_own_pending(
            before.pending_transaction_id, case.user.id
        )
    assert result is None
    assert (
        await transaction_repository.get_by_id(before.pending_transaction_id)
    ).status is TransactionStatus.PENDING
    after = await case.repository.get(case.subscription.id)
    assert after.pending_transaction_id == before.pending_transaction_id and after.enabled
    assert await case.repository.consent_terms(after.consent_id) is not None


async def test_overdue_terminal_failure_does_not_send_another_final_notice(case, session, uow):
    case.provider.status = "canceled"
    case.provider.cancellation_reason = "card_expired"
    await case.worker.system()
    before = await _notice_types(session)
    async with uow:
        await session.execute(
            update(Subscription)
            .where(Subscription.id == case.subscription.id)
            .values(expire_at=datetime_now() - timedelta(days=10))
        )
        await case.repository.list_due(datetime_now(), due_before=datetime_now(), limit=100)
    assert await _notice_types(session) == before
    after = await case.repository.get(case.subscription.id)
    assert not after.enabled and after.last_error == "card_expired"


@pytest.mark.parametrize("consent", [False, True])
async def test_manual_renewal_before_unknown_retirement_keeps_the_future_cycle_available(
    case, session, uow, transaction_repository, consent
):
    case.provider.lose_response = True
    await case.worker.system()
    before = await case.repository.get(case.subscription.id)
    await cases._manual_renewal(case, transaction_repository, session, uow, consent=consent)
    async with uow:
        await session.execute(
            update(Transaction)
            .where(Transaction.id == before.pending_transaction_id)
            .values(created_at=datetime_now() - timedelta(hours=24))
        )
    await cases._tick_again(case, uow)
    after = await case.repository.get(case.subscription.id)
    assert after.pending_transaction_id is None and after.submitted_at is None
    assert after.enabled and after.last_error is None
    state = await case.get_state(case.user, case.subscription.id)
    assert state.enabled and state.available and not state.paused
    await case.worker.system(case.subscription.id)
    assert len(case.provider.posts) == 1
    assert (
        await transaction_repository.get_by_id(before.pending_transaction_id)
    ).status is TransactionStatus.FAILED
