import pytest
from sqlalchemy import select, update

from app.core.db.models import EventOutboxEntry, RecurringConsent, RecurringPayment
from app.core.enums import Role, TransactionStatus
from app.core.exceptions import ConflictError, PermissionDeniedError, ValidationError
from app.modules.transactions.recurring_admin import ManageRecurringPaymentDto
from app.modules.transactions.recurring_dto import SetRecurringPaymentDto
from app.modules.transactions.usecases.manage_recurring_payment import ManageRecurringPaymentUseCase
from app.modules.users.dto import CreateUserDto
from tests.modules.transactions import test_recurring_payments as cases

case = cases.case


@pytest.fixture(autouse=True)
def production_session_mode(session):
    session.autoflush = False


@pytest.fixture
async def manager(
    case, transaction_repository, subscription_repository, user_repository, event_publisher, uow
):
    async with uow:
        operator = await user_repository.create(
            CreateUserDto(name="Recurring operator", role=Role.OWNER)
        )
    return ManageRecurringPaymentUseCase(
        case.repository,
        transaction_repository,
        subscription_repository,
        user_repository,
        case.worker,
        event_publisher,
        uow,
    ), operator


async def _audit(session):
    return list(
        await session.scalars(
            select(EventOutboxEntry).where(
                EventOutboxEntry.event_type == "RecurringPaymentManagedEvent"
            )
        )
    )


async def test_operator_checks_a_timed_out_payment_without_starting_a_new_charge(
    case, manager, session, uow, transaction_repository
):
    action, operator = manager
    case.provider.status = "pending"
    await case.worker.system()
    before = await case.repository.get(case.subscription.id)
    async with uow:
        await case.repository.pause(case.subscription.id, "pending_timeout")
    case.provider.status = "succeeded"
    await action(
        operator,
        ManageRecurringPaymentDto(
            subscription_id=case.subscription.id,
            action="check",
            expected_pending_transaction_id=before.pending_transaction_id,
            client_ip="127.0.0.1",
        ),
    )
    paid = await transaction_repository.get_by_id(before.pending_transaction_id)
    assert paid.status is TransactionStatus.PAID
    assert len(case.provider.posts) == 1 and len(case.dispatch.messages) == 1
    entries = await _audit(session)
    assert len(entries) == 1 and entries[0].actor_id == operator.id
    assert entries[0].payload["action"] == "check" and entries[0].ip_address == "127.0.0.1"


async def test_operator_close_revokes_consent_but_preserves_a_late_paid_fulfillment(
    case, manager, session, uow, transaction_repository
):
    action, operator = manager
    case.provider.status = "pending"
    await case.worker.system()
    before = await case.repository.get(case.subscription.id)
    await action(
        operator,
        ManageRecurringPaymentDto(
            subscription_id=case.subscription.id,
            action="close",
            expected_pending_transaction_id=before.pending_transaction_id,
        ),
    )
    closed = await case.repository.get(case.subscription.id)
    assert not closed.enabled and closed.last_error == "admin_closed"
    assert closed.pending_transaction_id is None and closed.submitted_at is not None
    assert (await session.get(RecurringConsent, before.consent_id)).revoked_at is not None
    order = await transaction_repository.get_by_id(before.pending_transaction_id)
    assert order.status is TransactionStatus.FAILED
    case.provider.status = "succeeded"
    async with uow:
        gateway = await case.worker._gateway()
    await case.worker._poll(case.subscription.id, order, gateway)
    assert (await transaction_repository.get_by_id(order.id)).status is TransactionStatus.PAID
    async with uow:
        await transaction_repository.mark_fulfilled(order.id, case.subscription.id)
    state = await case.get_state(case.user, case.subscription.id)
    assert not state.enabled and not state.can_disable and state.available
    assert (await case.repository.get(case.subscription.id)).submitted_at is None
    assert len(case.provider.posts) == 1 and len(await _audit(session)) == 1


async def test_operator_cannot_apply_close_to_a_replaced_pending_order(case, manager, session):
    action, operator = manager
    case.provider.status = "pending"
    await case.worker.system()
    before = await case.repository.get(case.subscription.id)
    with pytest.raises(ConflictError):
        await action(
            operator,
            ManageRecurringPaymentDto(
                subscription_id=case.subscription.id,
                action="close",
                expected_pending_transaction_id=before.pending_transaction_id + 1,
            ),
        )
    after = await case.repository.get(case.subscription.id)
    assert after.pending_transaction_id == before.pending_transaction_id and after.enabled
    assert not await _audit(session)


async def test_operator_retry_requeues_a_corrected_shop_error_without_touching_consent(
    case, manager, session
):
    action, operator = manager
    case.provider.reject = True
    await case.worker.system()
    before = await case.repository.get(case.subscription.id)
    assert before.last_error == "provider_configuration_error"
    await action(
        operator, ManageRecurringPaymentDto(subscription_id=case.subscription.id, action="retry")
    )
    after = await case.repository.get(case.subscription.id)
    assert after.enabled and after.last_error is None and after.consent_id == before.consent_id
    assert len(case.provider.posts) == 1
    case.provider.reject = False
    await case.worker.system()
    assert len(case.provider.posts) == 2 and len(await _audit(session)) == 1


@pytest.mark.parametrize(
    "reason", ["retries_exhausted", "payment_status_unknown", "permission_revoked"]
)
async def test_operator_retry_cannot_bypass_terminal_payment_limits(
    case, manager, reason, session, uow
):
    action, operator = manager
    async with uow:
        await session.execute(
            update(RecurringPayment)
            .where(RecurringPayment.subscription_id == case.subscription.id)
            .values(last_error=reason, retry_count=9)
        )
    with pytest.raises(ValidationError):
        await action(
            operator,
            ManageRecurringPaymentDto(subscription_id=case.subscription.id, action="retry"),
        )
    assert not case.provider.posts and not await _audit(session)


async def test_operator_retry_cannot_override_customer_withdrawal(case, manager, session):
    action, operator = manager
    await case.set_state(
        case.user, SetRecurringPaymentDto(subscription_id=case.subscription.id, enabled=False)
    )
    with pytest.raises(ValidationError):
        await action(
            operator,
            ManageRecurringPaymentDto(subscription_id=case.subscription.id, action="retry"),
        )
    assert (await case.repository.get(case.subscription.id)).customer_disabled
    assert not case.provider.posts and not await _audit(session)


async def test_customer_cannot_manage_an_autopayment_without_operator_permission(case, manager):
    action, _ = manager
    with pytest.raises(PermissionDeniedError):
        await action(
            case.user,
            ManageRecurringPaymentDto(subscription_id=case.subscription.id, action="retry"),
        )
    assert not case.provider.posts


async def test_late_verified_cancellation_resolves_operator_closed_payment_without_reenabling(
    case, manager, session, uow, transaction_repository
):
    action, operator = manager
    case.provider.status = "pending"
    await case.worker.system()
    before = await case.repository.get(case.subscription.id)
    await action(
        operator,
        ManageRecurringPaymentDto(
            subscription_id=case.subscription.id,
            action="close",
            expected_pending_transaction_id=before.pending_transaction_id,
        ),
    )
    case.provider.status = "canceled"
    order = await transaction_repository.get_by_id(before.pending_transaction_id)
    async with uow:
        gateway = await case.worker._gateway()
    await case.worker._poll(case.subscription.id, order, gateway)
    after = await case.repository.get(case.subscription.id)
    assert after.submitted_at is None and not after.enabled
    assert after.last_error == "admin_closed"
    assert (await transaction_repository.get_by_id(order.id)).status is TransactionStatus.CANCELED
    assert not (await case.get_state(case.user, case.subscription.id)).can_disable
    assert len(case.provider.posts) == 1
