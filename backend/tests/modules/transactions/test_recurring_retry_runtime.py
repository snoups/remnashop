import json
from dataclasses import fields, replace
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, update

from app.core.db.models import RecurringPayment, Subscription, Transaction
from app.core.enums import Currency, PaymentGatewayType, PurchaseType, TransactionStatus
from app.core.utils.time import datetime_now
from app.modules.transactions.dto import CreateTransactionDto, HandleWebhookDto, WebhookRequest
from app.modules.transactions.recurring_dto import SetRecurringPaymentDto
from app.modules.transactions.usecases import HandlePaymentWebhookUseCase
from tests.fakes.events import RecordingEventPublisher
from tests.modules.transactions import test_recurring_payments as recurring_cases
from tests.modules.transactions.test_recurring_payments import _tick_again

case = recurring_cases.case


async def _age_retry(case, session, uow, retry_count):
    offsets = (1, 3, 6, 12, 24, 36, 48, 72)
    first = datetime_now() - timedelta(hours=offsets[retry_count - 1], minutes=1)
    expiry = first + timedelta(days=1)
    async with uow:
        await session.execute(
            update(RecurringPayment)
            .where(RecurringPayment.subscription_id == case.subscription.id)
            .values(
                first_failure_at=first,
                bank_retry_at=first + timedelta(hours=offsets[retry_count - 1]),
                retry_count=retry_count,
                cycle_expire_at=expiry,
                next_attempt_at=datetime_now() - timedelta(seconds=1),
            )
        )
        await session.execute(
            update(Subscription)
            .where(Subscription.id == case.subscription.id)
            .values(expire_at=expiry)
        )
    return first


async def _manual_stars_renewal(case, transaction_repository, session, uow):
    values = {
        field.name: getattr(case.source, field.name) for field in fields(CreateTransactionDto)
    }
    values.update(
        idempotency_key="manual-stars-" + str(case.source.id),
        gateway_type=PaymentGatewayType.TELEGRAM_STARS,
        currency=Currency.XTR,
        purchase_type=PurchaseType.RENEW,
        target_subscription_id=case.subscription.id,
        recurring_consent_id=None,
        final_price=Decimal("100"),
        plan_snapshot=replace(
            case.source.plan_snapshot, currency=Currency.XTR, price_paid=Decimal("100")
        ),
    )
    if "recurring_consent" in values:
        values["recurring_consent"] = False
    async with uow:
        order = await transaction_repository.create(CreateTransactionDto(**values))
        await transaction_repository.mark_status(order.id, TransactionStatus.PAID)
        await session.execute(
            update(Subscription)
            .where(Subscription.id == case.subscription.id)
            .values(expire_at=datetime_now() + timedelta(days=30))
        )
        await transaction_repository.mark_fulfilled(order.id, case.subscription.id)
    return order


@pytest.mark.parametrize("reject_code", [401, 403])
async def test_merchant_credentials_failure_keeps_authorization_and_bank_retry_budget(
    case,
    reject_code,
    uow,
):
    case.provider.reject = True
    case.provider.reject_code = reject_code
    await case.worker.system()
    mandate = await case.repository.get(case.subscription.id)
    assert mandate.enabled and not mandate.customer_disabled
    assert mandate.pending_transaction_id is None
    assert mandate.first_failure_at is None and mandate.retry_count == 0
    assert mandate.last_error == "merchant_unavailable"
    assert mandate.next_attempt_at > datetime_now()
    assert len(case.provider.posts) == 1
    first_key = case.provider.posts[0].headers["Idempotence-Key"]
    case.provider.reject = False
    await _tick_again(case, uow)
    after = await case.repository.get(case.subscription.id)
    assert after.enabled and after.first_failure_at is None and after.retry_count == 0
    assert len(case.provider.posts) == 2
    assert case.provider.posts[1].headers["Idempotence-Key"] != first_key


async def test_request_configuration_error_never_consumes_bank_retries(case, uow):
    case.provider.reject = True
    await case.worker.system()
    initial = await case.repository.get(case.subscription.id)
    assert initial.enabled and initial.retry_count == 0
    assert initial.pending_transaction_id is None and initial.first_failure_at is None
    assert initial.last_error == "provider_configuration_error"
    await _tick_again(case, uow)
    assert len(case.provider.posts) == 1


async def test_bank_decline_schedules_a_retry_without_switching_off_the_customer_preference(
    case,
    uow,
):
    case.provider.status = "canceled"
    case.provider.cancellation_reason = "insufficient_funds"
    await case.worker.system()
    mandate = await case.repository.get(case.subscription.id)
    assert mandate.enabled and mandate.pending_transaction_id is None
    assert mandate.first_failure_at is not None and mandate.retry_count == 1
    assert mandate.next_attempt_at == mandate.first_failure_at + timedelta(hours=1)
    assert mandate.last_error == "insufficient_funds"
    await _tick_again(case, uow)
    assert len(case.provider.posts) == 1


@pytest.mark.parametrize("retry_count", range(1, 9))
async def test_each_bank_retry_uses_the_persisted_first_failure_anchor(
    case,
    session,
    uow,
    retry_count,
):
    case.provider.status = "canceled"
    case.provider.cancellation_reason = "insufficient_funds"
    await case.worker.system()
    first_key = case.provider.posts[0].headers["Idempotence-Key"]
    first = await _age_retry(case, session, uow, retry_count)
    await case.worker.system()
    mandate = await case.repository.get(case.subscription.id)
    assert len(case.provider.posts) == 2
    assert case.provider.posts[1].headers["Idempotence-Key"] != first_key
    assert mandate.first_failure_at == first
    assert mandate.retry_count == retry_count + 1
    assert mandate.enabled and mandate.pending_transaction_id is None
    offsets = (1, 3, 6, 12, 24, 36, 48, 72)
    if retry_count < len(offsets):
        assert mandate.next_attempt_at == first + timedelta(hours=offsets[retry_count])
    else:
        assert mandate.last_error == "retries_exhausted"
        future = datetime_now() + timedelta(days=7)
        assert case.subscription.id not in await case.repository.list_due(
            future, due_before=future, limit=100
        )


async def test_a_cancellation_webhook_before_cron_still_schedules_a_bank_retry(
    case,
    transaction_repository,
    gateway_repository,
    user_repository,
    uow,
):
    case.provider.status = "pending"
    await case.worker.system()
    mandate = await case.repository.get(case.subscription.id)
    order = await transaction_repository.get_by_id(mandate.pending_transaction_id)
    case.provider.status = "canceled"
    case.provider.cancellation_reason = "insufficient_funds"
    handler = HandlePaymentWebhookUseCase(
        transaction_repository,
        gateway_repository,
        case.worker._factory,
        user_repository,
        RecordingEventPublisher(),
        uow,
        case.dispatch,
    )
    await handler.system(
        HandleWebhookDto(
            gateway_type=PaymentGatewayType.YOOKASSA,
            request=WebhookRequest(
                body=json.dumps(
                    {
                        "event": "payment.canceled",
                        "object": {
                            "id": order.external_payment_id,
                            "metadata": {"order_ref": order.idempotency_key},
                        },
                    }
                ).encode(),
                headers={},
                client_ip="185.71.76.1",
            ),
        )
    )
    assert (await transaction_repository.get_by_id(order.id)).status is TransactionStatus.CANCELED
    await _tick_again(case, uow)
    after = await case.repository.get(case.subscription.id)
    assert after.enabled and after.pending_transaction_id is None
    assert after.retry_count == 1 and after.first_failure_at is not None
    assert after.next_attempt_at == after.first_failure_at + timedelta(hours=1)


async def test_a_long_pending_payment_is_parked_without_releasing_the_debit_lock(
    case,
    session,
    uow,
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
    await _tick_again(case, uow)
    parked = await case.repository.get(case.subscription.id)
    assert parked.last_error == "pending_timeout"
    assert parked.enabled and parked.pending_transaction_id == initial.pending_transaction_id
    count = len(case.provider.requests)
    future = datetime_now() + timedelta(minutes=5)
    assert case.subscription.id not in await case.repository.list_due(
        future, due_before=future, limit=100
    )
    later = datetime_now() + timedelta(hours=2)
    assert case.subscription.id in await case.repository.list_due(
        later, due_before=later, limit=100
    )
    assert len(case.provider.requests) == count
    assert len(case.provider.posts) == 1


async def test_a_stale_cancellation_cannot_clear_the_next_pending_attempt(
    case,
    transaction_repository,
    session,
    uow,
):
    case.provider.status = "canceled"
    case.provider.cancellation_reason = "insufficient_funds"
    await case.worker.system()
    reference = json.loads(case.provider.posts[0].content)["metadata"]["order_ref"]
    first_id = await session.scalar(
        select(Transaction.id).where(Transaction.idempotency_key == reference)
    )
    old = await transaction_repository.get_by_id(first_id)
    await _age_retry(case, session, uow, 1)
    case.provider.status = "pending"
    await case.worker.system()
    current = await case.repository.get(case.subscription.id)
    assert current.pending_transaction_id is not None and current.pending_transaction_id != old.id
    case.provider.status = "canceled"
    gateway = await case.worker._gateway()
    await case.worker._poll(case.subscription.id, old, gateway)
    after = await case.repository.get(case.subscription.id)
    assert after.pending_transaction_id == current.pending_transaction_id
    assert after.retry_count == current.retry_count
    assert after.first_failure_at == current.first_failure_at
    assert after.enabled


async def test_manual_stars_renewal_keeps_authorization_and_supersedes_an_unsent_attempt(
    case,
    transaction_repository,
    session,
    uow,
):
    original = await case.repository.get(case.subscription.id)
    await case.worker._reserve(original)
    reserved = await case.repository.get(case.subscription.id)
    assert reserved.pending_transaction_id is not None and reserved.submitted_at is None
    await _manual_stars_renewal(case, transaction_repository, session, uow)
    await _tick_again(case, uow)
    after = await case.repository.get(case.subscription.id)
    assert after.enabled and not after.customer_disabled
    assert after.source_transaction_id == original.source_transaction_id
    assert after.consent_id == original.consent_id
    assert after.payment_method_id == original.payment_method_id
    assert after.pending_transaction_id is None
    assert not case.provider.posts
    assert (
        await transaction_repository.get_by_id(reserved.pending_transaction_id)
    ).status is TransactionStatus.CANCELED


async def test_runtime_timing_changes_do_not_replace_the_accepted_charge_policy(
    case,
    session,
    uow,
    monkeypatch,
):
    original = await case.repository.get(case.subscription.id)
    accepted = await case.repository.consent_terms(original.consent_id)
    assert accepted.lead_minutes == 1440
    monkeypatch.setattr(case.worker._config.recurring, "lead_minutes", 60)
    monkeypatch.setattr(case.worker._config.recurring, "retry_minutes", 1)
    monkeypatch.setattr(case.worker._config.recurring, "max_overdue_hours", 1)
    expiry = datetime_now() + timedelta(hours=12)
    async with uow:
        await session.execute(
            update(Subscription)
            .where(Subscription.id == case.subscription.id)
            .values(expire_at=expiry)
        )
    state = await case.get_state(case.user, case.subscription.id)
    assert state.enabled and state.available
    assert state.next_payment_at == expiry - timedelta(minutes=accepted.lead_minutes)
    await case.worker.system()
    assert len(case.provider.posts) == 1
    after = await case.repository.get(case.subscription.id)
    assert after.enabled and after.last_error != "consent_required"


async def test_runtime_window_increase_does_not_widen_the_accepted_limit(
    case,
    session,
    uow,
    monkeypatch,
):
    original = await case.repository.get(case.subscription.id)
    accepted = await case.repository.consent_terms(original.consent_id)
    monkeypatch.setattr(case.worker._config.recurring, "max_overdue_hours", 168)
    async with uow:
        await session.execute(
            update(Subscription)
            .where(Subscription.id == case.subscription.id)
            .values(expire_at=datetime_now() - timedelta(hours=accepted.max_overdue_hours + 1))
        )
    await case.worker.system()
    assert not case.provider.posts
    after = await case.repository.get(case.subscription.id)
    assert not after.enabled and after.last_error == "renewal_window_expired"


async def test_auth_failure_after_a_lost_create_keeps_the_original_key_and_attempt(
    case,
    uow,
):
    case.provider.lose_response = True
    await case.worker.system()
    original = await case.repository.get(case.subscription.id)
    assert original.pending_transaction_id is not None
    case.provider.reject = True
    case.provider.reject_code = 401
    await _tick_again(case, uow)
    ambiguous = await case.repository.get(case.subscription.id)
    assert ambiguous.pending_transaction_id == original.pending_transaction_id
    assert ambiguous.enabled and ambiguous.first_failure_at is None and ambiguous.retry_count == 0
    assert len(case.provider.posts) == 2
    assert len({request.headers["Idempotence-Key"] for request in case.provider.posts}) == 1
    case.provider.reject = False
    await _tick_again(case, uow)
    assert len(case.provider.posts) == 3
    assert len({request.headers["Idempotence-Key"] for request in case.provider.posts}) == 1
    assert len(case.provider.keys) == 1
    assert len(case.dispatch.messages) == 1


async def test_manual_stars_renewal_does_not_repost_an_ambiguous_old_attempt(
    case,
    transaction_repository,
    session,
    uow,
):
    case.provider.lose_response = True
    await case.worker.system()
    original = await case.repository.get(case.subscription.id)
    await _manual_stars_renewal(case, transaction_repository, session, uow)
    await _tick_again(case, uow)
    assert len(case.provider.posts) == 1
    async with uow:
        await session.execute(
            update(Transaction)
            .where(Transaction.id == original.pending_transaction_id)
            .values(created_at=datetime_now() - timedelta(hours=24))
        )
    await _tick_again(case, uow)
    after = await case.repository.get(case.subscription.id)
    assert after.enabled and after.pending_transaction_id is None
    assert after.source_transaction_id == original.source_transaction_id
    assert after.consent_id == original.consent_id
    assert len(case.provider.posts) == 1


async def test_provider_side_withdrawal_cannot_be_retried_with_the_saved_method(
    case,
    session,
    uow,
):
    case.provider.status = "canceled"
    case.provider.cancellation_reason = "permission_revoked"
    original = await case.repository.get(case.subscription.id)
    await case.worker.system()
    after = await case.repository.get(case.subscription.id)
    assert not after.enabled and after.payment_method_id is None
    assert after.pending_transaction_id is None
    assert after.last_error == "permission_revoked"
    assert await case.repository.consent_terms(original.consent_id) is None
    await _tick_again(case, uow)
    assert len(case.provider.posts) == 1


async def test_a_late_decline_skips_retry_slots_that_have_already_passed(
    case,
    session,
    uow,
):
    case.provider.status = "canceled"
    case.provider.cancellation_reason = "insufficient_funds"
    await case.worker.system()
    first = datetime_now() - timedelta(hours=7)
    expiry = first + timedelta(days=1)
    async with uow:
        await session.execute(
            update(RecurringPayment)
            .where(RecurringPayment.subscription_id == case.subscription.id)
            .values(
                first_failure_at=first,
                bank_retry_at=first + timedelta(hours=1),
                retry_count=1,
                cycle_expire_at=expiry,
                next_attempt_at=datetime_now() - timedelta(seconds=1),
            )
        )
        await session.execute(
            update(Subscription)
            .where(Subscription.id == case.subscription.id)
            .values(expire_at=expiry)
        )
    await case.worker.system()
    after = await case.repository.get(case.subscription.id)
    assert after.first_failure_at == first and after.retry_count == 2
    assert after.next_attempt_at == first + timedelta(hours=12)
    assert after.bank_retry_at == first + timedelta(hours=12)
    assert len(case.provider.posts) == 2
    # A task queued before the decline must respect the newly scheduled retry.
    await case.worker.system(case.subscription.id)
    assert len(case.provider.posts) == 2


async def test_switching_off_and_on_cannot_erase_a_pending_timeout(
    case,
    session,
    uow,
):
    case.provider.status = "pending"
    await case.worker.system()
    original = await case.repository.get(case.subscription.id)
    async with uow:
        await session.execute(
            update(RecurringPayment)
            .where(RecurringPayment.subscription_id == case.subscription.id)
            .values(pending_since=datetime_now() - timedelta(hours=25))
        )
    await _tick_again(case, uow)
    assert (await case.repository.get(case.subscription.id)).last_error == "pending_timeout"
    disabled = await case.set_state(
        case.user, SetRecurringPaymentDto(subscription_id=case.subscription.id, enabled=False)
    )
    assert disabled.customer_disabled and not disabled.enabled and disabled.available
    assert disabled.last_error == "customer_disabled"
    await case.set_state(
        case.user,
        SetRecurringPaymentDto(
            subscription_id=case.subscription.id,
            enabled=True,
            terms_id=disabled.terms.terms_id,
        ),
    )
    after = await case.repository.get(case.subscription.id)
    assert after.pending_transaction_id == original.pending_transaction_id
    assert len(case.provider.posts) == 1


async def test_late_verified_success_resumes_the_original_authorization_without_a_new_charge(
    case,
    transaction_repository,
    gateway_repository,
    user_repository,
    session,
    uow,
):
    old_id = await recurring_cases._lose_recurring_payment(case, session, uow)
    order = await transaction_repository.get_by_id(old_id)
    payment_id = case.provider.keys[order.idempotency_key]
    grant_id = (await case.repository.get(case.subscription.id)).consent_id
    await _tick_again(case, uow)
    blocked = await case.repository.get(case.subscription.id)
    assert not blocked.enabled and blocked.last_error == "payment_status_unknown"
    handler = HandlePaymentWebhookUseCase(
        transaction_repository,
        gateway_repository,
        case.worker._factory,
        user_repository,
        RecordingEventPublisher(),
        uow,
        case.dispatch,
    )
    await handler.system(
        HandleWebhookDto(
            gateway_type=PaymentGatewayType.YOOKASSA,
            request=WebhookRequest(
                body=json.dumps(
                    {
                        "event": "payment.succeeded",
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
    )
    async with uow:
        await session.execute(
            update(Subscription)
            .where(Subscription.id == case.subscription.id)
            .values(expire_at=datetime_now() + timedelta(days=30))
        )
        await transaction_repository.mark_fulfilled(old_id, case.subscription.id)
    restored = await case.repository.get(case.subscription.id)
    assert restored.enabled and restored.last_error is None
    assert restored.consent_id == grant_id and restored.pending_transaction_id is None
    assert len(case.provider.posts) == 1


@pytest.mark.parametrize("reserved", [False, True])
async def test_paid_manual_renewal_waiting_for_fulfillment_prevents_an_auto_debit(
    case,
    transaction_repository,
    session,
    uow,
    reserved,
):
    if reserved:
        await case.worker._reserve(await case.repository.get(case.subscription.id))
    values = {
        field.name: getattr(case.source, field.name) for field in fields(CreateTransactionDto)
    }
    values.update(
        idempotency_key="paid-manual-waiting-" + str(case.source.id),
        gateway_type=PaymentGatewayType.TELEGRAM_STARS,
        currency=Currency.XTR,
        purchase_type=PurchaseType.RENEW,
        target_subscription_id=case.subscription.id,
        recurring_consent_id=None,
        recurring_consent=False,
    )
    async with uow:
        order = await transaction_repository.create(CreateTransactionDto(**values))
        await transaction_repository.mark_status(order.id, TransactionStatus.PAID)
    await case.worker.system()
    assert not case.provider.posts
    before = await case.repository.get(case.subscription.id)
    assert before.enabled and before.submitted_at is None
    async with uow:
        await session.execute(
            update(Subscription)
            .where(Subscription.id == case.subscription.id)
            .values(expire_at=datetime_now() + timedelta(days=30))
        )
        await transaction_repository.mark_fulfilled(order.id, case.subscription.id)
    await case.worker.system()
    after = await case.repository.get(case.subscription.id)
    assert after.enabled and after.pending_transaction_id is None
    assert not case.provider.posts
