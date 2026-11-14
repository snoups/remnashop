from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import update

from app.core.db.models import RecurringPayment
from app.core.utils.time import datetime_now
from app.modules.transactions.tasks import (
    process_one_recurring_payment_task,
    process_recurring_payments_task,
)
from app.modules.transactions.usecases.enqueue_recurring_payments import (
    EnqueueRecurringPaymentsUseCase,
)
from tests.fakes.dispatch import RecordingDispatch
from tests.modules.transactions import test_recurring_payments

case = test_recurring_payments.case


class _Queue:
    def __init__(self, session, *, fail=False):
        self.session = session
        self.fail = fail
        self.messages = []
        self.transactions = []

    async def kiq(self, *, subscription_id: int):
        self.messages.append(subscription_id)
        self.transactions.append(self.session.in_transaction())
        if self.fail:
            raise RuntimeError("private-provider-response")


async def test_scheduler_commits_claim_before_dispatch_and_does_not_enqueue_twice(
    case,
    session,
    uow,
    config,
):
    before = await case.repository.get(case.subscription.id)
    queue = _Queue(session)
    scheduler = EnqueueRecurringPaymentsUseCase(case.repository, queue, uow, config)
    await scheduler.system()
    await scheduler.system()
    assert queue.messages == [case.subscription.id]
    assert queue.transactions == [False]
    mandate = await case.repository.get(case.subscription.id)
    assert mandate.leased_until > datetime_now()
    assert mandate.next_attempt_at == before.next_attempt_at
    assert not case.provider.posts


async def test_scheduler_can_recover_a_broker_failure_after_its_lease_expires(
    case,
    session,
    uow,
    config,
    capfd,
):
    before = await case.repository.get(case.subscription.id)
    queue = _Queue(session, fail=True)
    scheduler = EnqueueRecurringPaymentsUseCase(case.repository, queue, uow, config)
    await scheduler.system()
    await scheduler.system()
    assert queue.messages == [case.subscription.id]
    assert "private-provider-response" not in capfd.readouterr().err
    leased = await case.repository.get(case.subscription.id)
    assert leased.leased_until > datetime_now()
    assert leased.next_attempt_at == before.next_attempt_at
    async with uow:
        await session.execute(
            update(RecurringPayment)
            .where(RecurringPayment.subscription_id == case.subscription.id)
            .values(leased_until=datetime_now() - timedelta(seconds=1))
        )
    queue.fail = False
    await scheduler.system()
    assert queue.messages == [case.subscription.id, case.subscription.id]
    assert queue.transactions == [False, False]


async def test_scheduler_uses_a_separate_quota_for_real_pending_polls(case, uow, config):
    case.provider.status = "pending"
    await case.worker.system(case.subscription.id)
    mandate = await case.repository.get(case.subscription.id)
    assert mandate.pending_transaction_id is not None
    async with uow:
        await case.repository.defer(case.subscription.id, datetime_now() - timedelta(seconds=1))
    queue = RecordingDispatch()
    await EnqueueRecurringPaymentsUseCase(case.repository, queue, uow, config).system()
    assert queue.messages == [{"subscription_id": case.subscription.id}]
    assert len(case.provider.posts) == 1


async def test_new_charges_are_enqueued_before_polls_with_independent_batch_limits(
    uow,
    config,
    monkeypatch,
):
    monkeypatch.setattr(config.recurring, "batch_size", 2)
    monkeypatch.setattr(config.recurring, "poll_batch_size", 3)
    monkeypatch.setattr(config.recurring, "notice_lead_minutes", 0)
    repository = MagicMock(list_due=AsyncMock(side_effect=[[11, 12], [21, 22, 23]]))
    queue = RecordingDispatch()
    await EnqueueRecurringPaymentsUseCase(repository, queue, uow, config).system()
    assert queue.messages == [{"subscription_id": value} for value in (11, 12, 21, 22, 23)]
    debit, poll = repository.list_due.await_args_list
    assert debit.kwargs["pending"] is False and debit.kwargs["limit"] == 2
    assert poll.kwargs["pending"] is True and poll.kwargs["limit"] == 3
    assert debit.kwargs["due_before"] - debit.args[0] == timedelta(minutes=1440)
    assert debit.kwargs["claim_until"] - debit.args[0] == timedelta(
        minutes=config.recurring.queue_lease_minutes
    )


async def test_no_jobs_are_published_when_the_claim_transaction_fails(uow, config, monkeypatch):
    repository = MagicMock(
        list_due=AsyncMock(side_effect=[[11], RuntimeError("database unavailable")])
    )
    queue = RecordingDispatch()
    with pytest.raises(RuntimeError, match="database unavailable"):
        await EnqueueRecurringPaymentsUseCase(repository, queue, uow, config).system()
    assert not queue.messages


async def test_scheduled_task_only_enqueues_work_and_each_child_receives_its_subscription():
    scheduler = AsyncMock()
    await process_recurring_payments_task.original_func.__dishka_orig_func__(use_case=scheduler)
    scheduler.system.assert_awaited_once_with()
    worker = AsyncMock()
    await process_one_recurring_payment_task.original_func.__dishka_orig_func__(7, use_case=worker)
    worker.system.assert_awaited_once_with(7)
    assert process_one_recurring_payment_task.labels["retry_on_error"] is True
    assert process_one_recurring_payment_task.labels["max_retries"] == 3


async def test_the_scheduler_and_its_dispatch_resolve_in_the_real_container(test_container):
    async with test_container() as scope:
        assert isinstance(
            await scope.get(EnqueueRecurringPaymentsUseCase), EnqueueRecurringPaymentsUseCase
        )


async def test_technical_deferral_preserves_the_bank_retry_deadline_and_releases_lease(
    case,
    session,
    uow,
):
    bank_deadline = datetime_now() + timedelta(hours=1)
    technical_retry = datetime_now() + timedelta(minutes=5)
    async with uow:
        await session.execute(
            update(RecurringPayment)
            .where(RecurringPayment.subscription_id == case.subscription.id)
            .values(
                bank_retry_at=bank_deadline, leased_until=datetime_now() + timedelta(minutes=30)
            )
        )
        await case.repository.defer(case.subscription.id, technical_retry, "provider_unavailable")
    state = await case.repository.get(case.subscription.id)
    assert state.bank_retry_at == bank_deadline
    assert state.next_attempt_at == technical_retry
    assert state.leased_until is None


@pytest.mark.parametrize("reason", ["payment_status_unknown", "pending_timeout"])
async def test_preference_toggles_cannot_erase_an_unresolved_bank_outcome(case, uow, reason):
    original = await case.repository.get(case.subscription.id)
    async with uow:
        await case.repository.mark_submitted(case.subscription.id)
        await case.repository.pause(case.subscription.id, reason)
        await case.repository.set_enabled(case.subscription.id, False)
    disabled = await case.repository.get(case.subscription.id)
    assert not disabled.enabled and disabled.last_error == "customer_disabled"
    async with uow:
        await case.repository.set_enabled(
            case.subscription.id, True, consent_id=original.consent_id
        )
    blocked = await case.repository.get(case.subscription.id)
    assert not blocked.enabled and blocked.last_error == "payment_status_unknown"
    assert blocked.submitted_at is not None


async def test_fresh_enable_resets_the_bank_schedule_but_disable_keeps_retry_history(
    case,
    session,
    uow,
):
    original = await case.repository.get(case.subscription.id)
    bank_deadline = datetime_now() + timedelta(hours=1)
    first_failure = datetime_now() - timedelta(minutes=1)
    async with uow:
        await session.execute(
            update(RecurringPayment)
            .where(RecurringPayment.subscription_id == case.subscription.id)
            .values(
                bank_retry_at=bank_deadline,
                first_failure_at=first_failure,
                retry_count=2,
                leased_until=datetime_now() + timedelta(minutes=30),
            )
        )
        await case.repository.set_enabled(case.subscription.id, False)
    disabled = await case.repository.get(case.subscription.id)
    assert disabled.bank_retry_at == bank_deadline and disabled.retry_count == 2
    assert disabled.leased_until is None
    async with uow:
        await case.repository.set_enabled(
            case.subscription.id, True, consent_id=original.consent_id
        )
    enabled = await case.repository.get(case.subscription.id)
    assert enabled.enabled and enabled.bank_retry_at is None
    assert enabled.first_failure_at is None and enabled.retry_count == 0
    assert enabled.leased_until is None
