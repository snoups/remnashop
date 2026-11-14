from dataclasses import fields
from datetime import timedelta
from uuid import uuid4

import httpx
import pytest

import app.modules.transactions.recurring_repository as recurring_repository_module
from app.core.enums import TransactionStatus
from app.core.utils.time import datetime_now
from app.modules.transactions.dto import CreateTransactionDto
from tests.modules.transactions import test_recurring_payments

case = test_recurring_payments.case


async def _prepare(case):
    mandate = await case.repository.get(case.subscription.id)
    await case.worker._reserve(mandate)
    context = await case.worker._pending_context(case.subscription.id)
    assert context is not None
    return context


@pytest.mark.parametrize("code", [200, 400, 401, 403, 404])
async def test_submission_persists_the_outcome_before_releasing_authorization(
    case, transaction_repository, code
):
    _, order, _ = await _prepare(case)
    case.provider.reject = code != 200
    case.provider.reject_code = code

    result = await case.worker._submit_if_authorized(
        case.subscription.id,
        order,
    )

    assert result is not None
    saved = await transaction_repository.get_by_id(order.id)
    current = await case.repository.get(case.subscription.id)
    if code == 200:
        assert saved.status is TransactionStatus.PENDING
        assert saved.external_payment_id == result[2].payment_id
        assert current.pending_transaction_id == order.id
    else:
        assert saved.status is TransactionStatus.FAILED
        assert saved.external_payment_id is None
        assert current.pending_transaction_id is None
    error = current.last_error
    case.provider.reject = False

    # The queued task may still carry the original, unsent order DTO and first flag.
    replay = await case.worker._submit_if_authorized(
        case.subscription.id,
        order,
    )

    assert replay is None
    assert len(case.provider.posts) == 1
    after = await case.repository.get(case.subscription.id)
    assert after.pending_transaction_id == current.pending_transaction_id
    assert after.last_error == error


@pytest.mark.parametrize("code", [400, 401])
async def test_delayed_first_preparation_cannot_retire_a_later_ambiguous_submission(
    case, transaction_repository, code
):
    initial, order, _ = await _prepare(case)
    later = await case.worker._pending_context(case.subscription.id)
    assert later is not None
    retry, retry_order, _ = later
    assert initial.submitted_at is None and retry.submitted_at is None
    case.provider.lose_response = True

    with pytest.raises(httpx.ReadTimeout):
        await case.worker._submit_if_authorized(
            case.subscription.id,
            retry_order,
        )

    first_marker = (await case.repository.get(case.subscription.id)).submitted_at
    assert first_marker is not None
    # The newer request reached YooKassa, so even a definite refusal for the delayed
    # first preparation cannot establish that this idempotency key was never charged.
    case.provider.reject = True
    case.provider.reject_code = code
    result = await case.worker._submit_if_authorized(
        case.subscription.id,
        order,
    )

    assert result is not None and result[2].outcome == "ambiguous"
    saved = await transaction_repository.get_by_id(order.id)
    current = await case.repository.get(case.subscription.id)
    assert saved.status is TransactionStatus.PENDING
    assert saved.external_payment_id is None
    assert current.pending_transaction_id == order.id
    assert current.submitted_at > first_marker
    assert current.enabled
    assert len(case.provider.posts) == 2
    assert len(case.provider.keys) == 1
    assert {request.headers["Idempotence-Key"] for request in case.provider.posts} == {
        order.idempotency_key
    }


async def test_submission_markers_advance_when_the_clock_is_frozen(case, monkeypatch):
    frozen = datetime_now()
    monkeypatch.setattr(recurring_repository_module, "datetime_now", lambda: frozen)
    _, order, _ = await _prepare(case)
    case.provider.lose_response = True
    with pytest.raises(httpx.ReadTimeout):
        await case.worker._submit_if_authorized(case.subscription.id, order)
    assert (await case.repository.get(case.subscription.id)).submitted_at == frozen
    result = await case.worker._submit_if_authorized(case.subscription.id, order)
    assert result is not None and result[2].outcome == "accepted"
    current = await case.repository.get(case.subscription.id)
    assert current.submitted_at == frozen + timedelta(microseconds=1)
    await case.worker._pending_context(case.subscription.id)
    assert (await case.repository.get(case.subscription.id)).submitted_at == current.submitted_at
    assert len(case.provider.keys) == 1


@pytest.mark.parametrize("code", [400, 401])
async def test_stale_submission_cannot_change_a_replacement_attempt(
    case, transaction_repository, uow, code
):
    _, old_order, _ = await _prepare(case)
    case.provider.reject = True
    case.provider.reject_code = code
    await case.worker._charge(
        case.subscription.id,
        old_order,
    )
    values = {field.name: getattr(old_order, field.name) for field in fields(CreateTransactionDto)}
    values["idempotency_key"] = uuid4().hex
    async with uow:
        replacement = await transaction_repository.create(CreateTransactionDto(**values))
        await case.repository.set_pending(
            case.subscription.id,
            replacement.id,
            expire_at=case.subscription.expire_at,
        )
        await case.repository.defer(
            case.subscription.id,
            datetime_now() + timedelta(minutes=5),
            "provider_unavailable",
        )
    case.provider.reject = False

    await case.worker._charge(
        case.subscription.id,
        old_order,
    )

    current = await case.repository.get(case.subscription.id)
    assert current.pending_transaction_id == replacement.id
    assert current.last_error == "provider_unavailable"
    assert len(case.provider.posts) == 1
