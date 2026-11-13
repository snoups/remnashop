import json
from dataclasses import dataclass, fields, replace
from datetime import timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select, text, update

from app.core.db.models import RecurringConsent, RecurringPayment, Subscription, Transaction
from app.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PlanType,
    PurchaseChannel,
    PurchaseType,
    SubscriptionStatus,
    TransactionStatus,
)
from app.core.exceptions import ValidationError
from app.core.utils.time import datetime_now
from app.modules.account_merge.repository import AccountMergeRepository
from app.modules.plans.dto import (
    CreatePlanDto,
    SetPlanDurationDto,
    SetPlanDurationsDto,
    UpdatePlanDto,
    UpdatePlanSquadsDto,
)
from app.modules.settings.dto import UpdateShopSettingsDto
from app.modules.subscriptions.dto import CreateSubscriptionDto, PlanSnapshot
from app.modules.subscriptions.tasks import purchase_subscription_task
from app.modules.subscriptions.usecases import FulfillPurchaseUseCase
from app.modules.transactions.checkout_pricing import CheckoutPricer
from app.modules.transactions.dto import (
    CreateTransactionDto,
    HandleWebhookDto,
    MarkOrderFulfilledDto,
    WebhookRequest,
)
from app.modules.transactions.gateways.base import PaymentHttpClient
from app.modules.transactions.gateways.factory import PaymentGatewayFactory
from app.modules.transactions.recurring_dto import SetRecurringPaymentDto
from app.modules.transactions.recurring_repository import RecurringPaymentRepository
from app.modules.transactions.recurring_terms import build_recurring_terms
from app.modules.transactions.usecases import (
    GetOwnRecurringPaymentUseCase,
    HandlePaymentWebhookUseCase,
    MarkOrderFulfilledUseCase,
    ProcessRecurringPaymentsUseCase,
    SetOwnRecurringPaymentUseCase,
)
from app.modules.users.dto import CreateUserDto
from tests.fakes.dispatch import RecordingDispatch
from tests.fakes.events import RecordingEventPublisher
from tests.fakes.remnawave import _user_payload
from tests.modules.subscriptions.factories import make_eligibility


class _YooKassa:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.keys: dict[str, str] = {}
        self.references: dict[str, str] = {}
        self.status = "succeeded"
        self.lose_response = False
        self.reject = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.method == "POST":
            if self.reject:
                return httpx.Response(400, json={"code": "invalid_payment_method"})
            key = request.headers["Idempotence-Key"]
            payment_id = self.keys.setdefault(key, f"payment-{len(self.keys) + 1}")
            self.references[payment_id] = json.loads(request.content)["metadata"]["order_ref"]
            if self.lose_response:
                self.lose_response = False
                raise httpx.ReadTimeout("response lost", request=request)
            return httpx.Response(200, json={"id": payment_id})
        payment_id = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(
            200,
            json={
                "id": payment_id,
                "status": self.status,
                "paid": self.status == "succeeded",
                "amount": {"value": "500.00", "currency": "RUB"},
                "metadata": {"order_ref": self.references[payment_id]},
                "payment_method": {"id": "method-token", "saved": True},
            },
        )

    @property
    def posts(self) -> list[httpx.Request]:
        return [request for request in self.requests if request.method == "POST"]


@dataclass
class _Case:
    worker: ProcessRecurringPaymentsUseCase
    repository: RecurringPaymentRepository
    get_state: GetOwnRecurringPaymentUseCase
    set_state: SetOwnRecurringPaymentUseCase
    user: Any
    subscription: Any
    source: Any
    provider: _YooKassa
    dispatch: RecordingDispatch


@pytest.fixture
async def case(
    session,
    uow,
    user_repository,
    subscription_repository,
    plan_repository,
    transaction_repository,
    gateway_repository,
    settings_repository,
    pricing_repository,
    promocode_repository,
    config,
):
    async with uow:
        user = await user_repository.create(
            CreateUserDto(name="recurring buyer", telegram_id=931001)
        )
        plan = await plan_repository.create(
            CreatePlanDto(
                name="Recurring plan",
                public_code="recurring-plan",
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
        snapshot = PlanSnapshot.from_plan(
            plan, price_paid=Decimal("400"), currency=Currency.RUB, duration_days=30
        )
        subscription = await subscription_repository.create(
            CreateSubscriptionDto(
                user_id=user.id,
                remnawave_user_id=931001,
                status=SubscriptionStatus.ACTIVE,
                traffic_limit=100,
                device_limit=3,
                expire_at=datetime_now() + timedelta(minutes=30),
                url="https://example.com/recurring",
                plan_snapshot=snapshot,
            )
        )
        await gateway_repository.update_settings(
            PaymentGatewayType.YOOKASSA,
            {
                "shop_id": "1000",
                "api_key": "test-key",
                "recurring_enabled": "true",
            },
        )
        await gateway_repository.set_active(PaymentGatewayType.YOOKASSA, True)
        consent_id = await RecurringPaymentRepository(session).record_consent(
            build_recurring_terms(
                config=config,
                user_id=user.id,
                plan_id=plan.id,
                target_subscription_id=None,
                purchase_type=PurchaseType.NEW,
                initial_amount=Decimal("400"),
                amount_limit=Decimal("500"),
                currency=Currency.RUB,
                duration_days=30,
                locale=user.language,
            ),
            channel=PurchaseChannel.BOT,
            telegram_id=user.telegram_id,
            event_id="initial-checkbox",
        )
        source = await transaction_repository.create(
            CreateTransactionDto(
                user_id=user.id,
                plan_id=plan.id,
                plan_snapshot=snapshot,
                duration_days=30,
                currency=Currency.RUB,
                purchase_type=PurchaseType.NEW,
                channel=PurchaseChannel.BOT,
                target_subscription_id=None,
                gateway_type=PaymentGatewayType.YOOKASSA,
                base_price=Decimal("500"),
                final_price=Decimal("400"),
                discount_percent=20,
                discount_source=DiscountSource.PURCHASE,
                anchor_base_price=Decimal("500"),
                anchor_final_price=Decimal("400"),
                customer_email="buyer@example.com",
                idempotency_key=uuid4().hex,
                expires_at=datetime_now(),
                recurring_consent=True,
                recurring_consent_id=consent_id,
            )
        )
        await transaction_repository.mark_status(source.id, TransactionStatus.PAID)
        await transaction_repository.remember_payment_method(source.id, "method-token", "1000")
        await transaction_repository.mark_fulfilled(source.id, subscription.id)
        # The original purchase predates the renewal cycle, as it does in production.
        paid_at = datetime_now() - timedelta(days=30)
        await session.execute(
            update(Transaction)
            .where(Transaction.id == source.id)
            .values(created_at=paid_at, updated_at=paid_at, fulfilled_at=paid_at)
        )
    repository = RecurringPaymentRepository(session)
    provider = _YooKassa()
    dispatch = RecordingDispatch()
    get_state = GetOwnRecurringPaymentUseCase(
        repository, transaction_repository, subscription_repository, gateway_repository, uow, config
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as http:
        worker = ProcessRecurringPaymentsUseCase(
            repository,
            transaction_repository,
            subscription_repository,
            user_repository,
            gateway_repository,
            settings_repository,
            CheckoutPricer(
                plan_repository,
                user_repository,
                make_eligibility(session),
                pricing_repository,
                uow,
                promocode_repository,
            ),
            PaymentGatewayFactory(config, PaymentHttpClient(http)),
            dispatch,
            uow,
            config,
        )
        yield _Case(
            worker,
            repository,
            get_state,
            SetOwnRecurringPaymentUseCase(repository, subscription_repository, get_state, uow),
            user,
            subscription,
            source,
            provider,
            dispatch,
        )


async def _tick_again(case: _Case, uow) -> None:
    async with uow:
        await case.repository.defer(case.subscription.id, datetime_now() - timedelta(seconds=1))
    await case.worker.system()


async def test_due_subscription_is_charged_once_and_dispatched_as_a_renewal(
    case, transaction_repository, uow
) -> None:
    await case.worker.system()
    await _tick_again(case, uow)
    assert len(case.provider.posts) == 1
    assert len(case.dispatch.messages) == 1
    mandate = await case.repository.get(case.subscription.id)
    order = await transaction_repository.get_by_id(mandate.pending_transaction_id)
    assert order.status is TransactionStatus.PAID
    assert order.is_recurring
    assert order.final_price == Decimal("500")
    assert order.discount_source is DiscountSource.NONE
    assert order.target_subscription_id == case.subscription.id
    assert case.dispatch.messages[0]["purchase_type"] == "RENEW"
    assert json.loads(case.provider.posts[0].content)["payment_method_id"] == "method-token"


async def test_lost_response_reuses_the_durable_key_after_restart(
    case, transaction_repository, uow
) -> None:
    case.provider.lose_response = True
    await case.worker.system()
    pending = await case.repository.get(case.subscription.id)
    first = await transaction_repository.get_by_id(pending.pending_transaction_id)
    assert first.external_payment_id is None
    await _tick_again(case, uow)
    assert len(case.provider.posts) == 2
    assert len(case.provider.keys) == 1
    assert len({request.headers["Idempotence-Key"] for request in case.provider.posts}) == 1
    assert len(case.dispatch.messages) == 1


async def test_an_expired_idempotency_key_is_never_sent_again(case, session, uow) -> None:
    case.provider.lose_response = True
    await case.worker.system()
    mandate = await case.repository.get(case.subscription.id)
    async with uow:
        await session.execute(
            update(Transaction)
            .where(Transaction.id == mandate.pending_transaction_id)
            .values(created_at=datetime_now() - timedelta(hours=24))
        )
    await _tick_again(case, uow)
    state = await case.get_state(case.user, case.subscription.id)
    assert not state.enabled
    assert state.last_error == "payment_status_unknown"
    assert len(case.provider.posts) == 1


async def test_customer_can_disable_and_enable_auto_renew(case, uow) -> None:
    await case.set_state(
        case.user, SetRecurringPaymentDto(subscription_id=case.subscription.id, enabled=False)
    )
    await case.worker.system()
    assert not case.provider.posts
    assert (await case.get_state(case.user, case.subscription.id)).customer_disabled
    await case.set_state(
        case.user,
        SetRecurringPaymentDto(
            subscription_id=case.subscription.id,
            enabled=True,
            terms_id=(await case.get_state(case.user, case.subscription.id)).terms.terms_id,
        ),
    )
    await _tick_again(case, uow)
    assert len(case.provider.posts) == 1


async def test_other_customers_cannot_read_or_disable_auto_renew(case, user_repository) -> None:
    other = await user_repository.create(CreateUserDto(name="other", telegram_id=931002))
    with pytest.raises(ValidationError):
        await case.get_state(other, case.subscription.id)
    with pytest.raises(ValidationError):
        await case.set_state(
            other, SetRecurringPaymentDto(subscription_id=case.subscription.id, enabled=False)
        )
    assert (await case.get_state(case.user, case.subscription.id)).enabled


async def test_disabling_shop_stops_new_requests_but_confirms_in_flight_payment(
    case, gateway_repository, uow
) -> None:
    case.provider.status = "pending"
    await case.worker.system()
    async with uow:
        await gateway_repository.update_settings(
            PaymentGatewayType.YOOKASSA, {"recurring_enabled": "false"}
        )
    case.provider.status = "succeeded"
    await _tick_again(case, uow)
    assert len(case.provider.posts) == 1
    assert len(case.dispatch.messages) == 1


@pytest.mark.parametrize("setting", ["recurring_enabled", "is_active"])
async def test_disabled_gateway_never_starts_a_charge(
    case, gateway_repository, uow, setting
) -> None:
    async with uow:
        if setting == "is_active":
            await gateway_repository.set_active(PaymentGatewayType.YOOKASSA, False)
        else:
            await gateway_repository.update_settings(
                PaymentGatewayType.YOOKASSA, {setting: "false"}
            )
    await case.worker.system()
    assert not case.provider.posts


async def test_a_price_above_the_agreed_limit_stops_auto_renew(case, plan_repository, uow) -> None:
    async with uow:
        await plan_repository.set_durations(
            SetPlanDurationsDto(
                plan_id=case.source.plan_id,
                durations=[SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("600"))],
            )
        )
    await case.worker.system()
    assert not case.provider.posts
    assert (await case.get_state(case.user, case.subscription.id)).last_error == "price_changed"


@pytest.mark.parametrize("status", [SubscriptionStatus.DELETED, SubscriptionStatus.DISABLED])
async def test_deleted_or_disabled_subscriptions_are_not_charged(
    case, session, uow, status
) -> None:
    async with uow:
        await session.execute(
            update(Subscription)
            .where(Subscription.id == case.subscription.id)
            .values(status=status)
        )
    await case.worker.system()
    assert not case.provider.posts


async def test_blocked_customer_is_not_charged(case, user_repository, uow) -> None:
    async with uow:
        await user_repository.set_blocked(case.user.id, True)
    await case.worker.system()
    assert not case.provider.posts


async def test_canceled_payment_disables_future_attempts(case, uow) -> None:
    case.provider.status = "canceled"
    await case.worker.system()
    await _tick_again(case, uow)
    assert len(case.provider.posts) == 1
    assert not case.dispatch.messages
    assert not (await case.get_state(case.user, case.subscription.id)).enabled


async def test_plaintext_tokens_are_not_stored_or_returned(case, session) -> None:
    stored = await session.scalar(
        text("SELECT payment_method_id FROM recurring_payments WHERE subscription_id = :id"),
        {"id": case.subscription.id},
    )
    state = await case.get_state(case.user, case.subscription.id)
    assert stored != "method-token"
    assert "method-token" not in state.model_dump_json()
    assert "method-token" not in repr(await case.repository.get(case.subscription.id))


async def test_fulfillment_moves_the_cycle_and_preserves_customer_opt_out(
    case, transaction_repository, session, uow
) -> None:
    await case.worker.system()
    mandate = await case.repository.get(case.subscription.id)
    await case.set_state(
        case.user, SetRecurringPaymentDto(subscription_id=case.subscription.id, enabled=False)
    )
    async with uow:
        await session.execute(
            update(Subscription)
            .where(Subscription.id == case.subscription.id)
            .values(expire_at=datetime_now() + timedelta(days=30))
        )
        await transaction_repository.mark_fulfilled(
            mandate.pending_transaction_id, case.subscription.id
        )
    await _tick_again(case, uow)
    assert len(case.provider.posts) == 1
    state = await case.get_state(case.user, case.subscription.id)
    assert not state.enabled and state.customer_disabled


async def test_delayed_manual_fulfillment_cannot_reenable_a_canceled_subscription(
    case, session, transaction_repository, uow
) -> None:
    async with uow:
        await session.execute(
            update(Transaction).where(Transaction.id == case.source.id).values(fulfilled_at=None)
        )
        await session.execute(
            update(RecurringPayment)
            .where(RecurringPayment.subscription_id == case.subscription.id)
            .values(source_transaction_id=None)
        )
    await case.set_state(
        case.user, SetRecurringPaymentDto(subscription_id=case.subscription.id, enabled=False)
    )
    async with uow:
        await transaction_repository.mark_fulfilled(case.source.id, case.subscription.id)
    state = await case.get_state(case.user, case.subscription.id)
    assert not state.enabled and state.customer_disabled
    await case.worker.system()
    assert not case.provider.posts


async def test_changing_shop_never_uses_a_method_from_another_merchant(
    case, gateway_repository, uow
) -> None:
    async with uow:
        await gateway_repository.update_settings(
            PaymentGatewayType.YOOKASSA, {"shop_id": "different"}
        )
    await case.worker.system()
    assert not case.provider.posts


async def test_new_cycle_waits_for_fulfillment_and_current_subscription_expiry(
    case, transaction_repository, session, uow
) -> None:
    await case.worker.system()
    mandate = await case.repository.get(case.subscription.id)
    async with uow:
        await session.execute(
            update(Subscription)
            .where(Subscription.id == case.subscription.id)
            .values(expire_at=datetime_now() + timedelta(days=30))
        )
        await transaction_repository.mark_fulfilled(
            mandate.pending_transaction_id, case.subscription.id
        )
    await _tick_again(case, uow)
    assert len(case.provider.posts) == 1
    async with uow:
        await session.execute(
            update(Subscription)
            .where(Subscription.id == case.subscription.id)
            .values(expire_at=datetime_now() + timedelta(minutes=30))
        )
    await _tick_again(case, uow)
    assert len(case.provider.posts) == 2
    assert len(case.provider.keys) == 2
    assert (
        await session.scalar(
            select(func.count()).select_from(Transaction).where(Transaction.is_recurring.is_(True))
        )
        == 2
    )


async def test_recurring_payment_runs_the_real_subscription_fulfillment_once(
    case,
    remnawave_store,
    purchase_subscription_use_case,
    user_repository,
    transaction_repository,
    subscription_repository,
    uow,
) -> None:
    remnawave_store[case.subscription.remnawave_user_id] = _user_payload(
        user_id=case.subscription.remnawave_user_id,
        username="recurring-buyer",
        expire_at=case.subscription.expire_at,
        active_internal_squads=[str(squad) for squad in case.source.plan_snapshot.internal_squads],
    )
    await case.worker.system()
    task = purchase_subscription_task.original_func.__dishka_orig_func__
    fulfill = FulfillPurchaseUseCase(
        user_repository, purchase_subscription_use_case, transaction_repository, uow
    )
    await task(**case.dispatch.messages[0], use_case=fulfill)
    first = await subscription_repository.get_by_id(case.subscription.id)
    await task(**case.dispatch.messages[0], use_case=fulfill)
    second = await subscription_repository.get_by_id(case.subscription.id)
    assert first.expire_at > case.subscription.expire_at + timedelta(days=29)
    assert second.expire_at == first.expire_at
    await MarkOrderFulfilledUseCase(transaction_repository, uow).system(
        MarkOrderFulfilledDto(
            payment_key=case.dispatch.messages[0]["idempotency_key"], subscription_id=first.id
        )
    )
    await _tick_again(case, uow)
    assert len(case.provider.posts) == 1


async def test_refunding_the_source_stops_future_charges(case, transaction_repository, uow) -> None:
    async with uow:
        await transaction_repository.mark_status(case.source.id, TransactionStatus.REFUNDED)
    await case.worker.system()
    assert not case.provider.posts


async def test_retry_preserves_receipt_after_a_gateway_settings_change(
    case, gateway_repository, uow
) -> None:
    async with uow:
        await gateway_repository.update_settings(PaymentGatewayType.YOOKASSA, {"vat_code": "1"})
    case.provider.lose_response = True
    await case.worker.system()
    async with uow:
        await gateway_repository.update_settings(PaymentGatewayType.YOOKASSA, {"vat_code": "2"})
    await _tick_again(case, uow)
    assert len(case.provider.posts) == 2
    assert case.provider.posts[0].content == case.provider.posts[1].content
    assert json.loads(case.provider.posts[1].content)["receipt"]["items"][0]["vat_code"] == 1


async def test_a_rejected_retry_cannot_establish_that_the_original_was_not_paid(
    case, transaction_repository, uow
) -> None:
    case.provider.lose_response = True
    await case.worker.system()
    pending = await case.repository.get(case.subscription.id)
    case.provider.reject = True
    await _tick_again(case, uow)
    mandate = await case.repository.get(case.subscription.id)
    order = await transaction_repository.get_by_id(pending.pending_transaction_id)
    assert order.status is TransactionStatus.FAILED
    assert mandate.pending_transaction_id is None
    assert mandate.last_error == "payment_status_unknown"
    assert not mandate.enabled


@pytest.mark.parametrize("original_email", [None, "previous-buyer@example.com"])
async def test_recurring_receipt_uses_current_shop_payment_email(
    case,
    settings_repository,
    gateway_repository,
    transaction_repository,
    session,
    uow,
    original_email,
) -> None:
    async with uow:
        await session.execute(
            update(Transaction)
            .where(Transaction.id == case.source.id)
            .values(customer_email=original_email)
        )
        await settings_repository.update_shop_settings(
            UpdateShopSettingsDto(
                payment_email="shop@example.com", fields_set=frozenset({"payment_email"})
            )
        )
        await gateway_repository.update_settings(PaymentGatewayType.YOOKASSA, {"vat_code": "1"})
    await case.worker.system()
    mandate = await case.repository.get(case.subscription.id)
    order = await transaction_repository.get_by_id(mandate.pending_transaction_id)
    assert order.customer_email == "shop@example.com"
    body = json.loads(case.provider.posts[0].content)
    assert body["receipt"]["customer"]["email"] == "shop@example.com"


async def test_retry_preserves_payment_email_after_shop_settings_change(
    case,
    settings_repository,
    gateway_repository,
    uow,
) -> None:
    async with uow:
        await settings_repository.update_shop_settings(
            UpdateShopSettingsDto(
                payment_email="first-shop@example.com", fields_set=frozenset({"payment_email"})
            )
        )
        await gateway_repository.update_settings(PaymentGatewayType.YOOKASSA, {"vat_code": "1"})
    case.provider.lose_response = True
    await case.worker.system()
    async with uow:
        await settings_repository.update_shop_settings(
            UpdateShopSettingsDto(
                payment_email="second-shop@example.com", fields_set=frozenset({"payment_email"})
            )
        )
    await _tick_again(case, uow)
    assert len(case.provider.posts) == 2
    assert case.provider.posts[0].content == case.provider.posts[1].content
    assert (
        json.loads(case.provider.posts[1].content)["receipt"]["customer"]["email"]
        == "first-shop@example.com"
    )


async def _lose_recurring_payment(case, session, uow):
    case.provider.lose_response = True
    await case.worker.system()
    mandate = await case.repository.get(case.subscription.id)
    order_id = mandate.pending_transaction_id
    async with uow:
        await session.execute(
            update(Transaction)
            .where(Transaction.id == order_id)
            .values(created_at=datetime_now() - timedelta(hours=24))
        )
    return order_id


async def _manual_renewal(case, transaction_repository, session, uow, *, consent=True):
    values = {
        field.name: getattr(case.source, field.name) for field in fields(CreateTransactionDto)
    }
    values.update(
        idempotency_key=uuid4().hex,
        purchase_type=PurchaseType.RENEW,
        target_subscription_id=case.subscription.id,
        discount_percent=0,
        discount_source=DiscountSource.NONE,
        final_price=Decimal("500"),
        anchor_final_price=Decimal("500"),
        plan_snapshot=replace(case.source.plan_snapshot, price_paid=Decimal("500")),
    )
    async with uow:
        values["recurring_consent"] = consent
        values["recurring_consent_id"] = (
            await case.repository.record_consent(
                build_recurring_terms(
                    config=case.worker._config,
                    user_id=case.user.id,
                    plan_id=case.source.plan_id,
                    target_subscription_id=case.subscription.id,
                    purchase_type=PurchaseType.RENEW,
                    initial_amount=Decimal("500"),
                    amount_limit=Decimal("500"),
                    currency=Currency.RUB,
                    duration_days=30,
                    locale=case.user.language,
                ),
                channel=PurchaseChannel.BOT,
                telegram_id=case.user.telegram_id,
                event_id="fresh-checkbox",
            )
            if consent
            else None
        )
        order = await transaction_repository.create(CreateTransactionDto(**values))
        await transaction_repository.mark_status(order.id, TransactionStatus.PAID)
        await transaction_repository.remember_payment_method(order.id, "fresh-method", "1000")
        await session.execute(
            update(Subscription)
            .where(Subscription.id == case.subscription.id)
            .values(expire_at=datetime_now() + timedelta(days=30))
        )
        await transaction_repository.mark_fulfilled(order.id, case.subscription.id)
    return await transaction_repository.get_by_id(order.id)


async def test_unknown_payment_leaves_the_active_queue(
    case, transaction_repository, session, uow
) -> None:
    order_id = await _lose_recurring_payment(case, session, uow)
    await _tick_again(case, uow)
    mandate = await case.repository.get(case.subscription.id)
    order = await transaction_repository.get_by_id(order_id)
    assert mandate.pending_transaction_id is None
    assert mandate.attempted_at is None
    assert not mandate.enabled
    assert mandate.last_error == "payment_status_unknown"
    assert order.status is TransactionStatus.FAILED
    future = datetime_now() + timedelta(days=2)
    assert case.subscription.id not in await case.repository.list_due(
        future, due_before=future, limit=100
    )
    await _tick_again(case, uow)
    assert len(case.provider.posts) == 1


async def test_manual_payment_restores_renewals_after_an_unknown_payment(
    case, transaction_repository, session, uow
) -> None:
    old_id = await _lose_recurring_payment(case, session, uow)
    await _tick_again(case, uow)
    manual = await _manual_renewal(case, transaction_repository, session, uow)
    mandate = await case.repository.get(case.subscription.id)
    assert mandate.source_transaction_id == manual.id
    assert mandate.pending_transaction_id is None
    assert mandate.enabled and mandate.last_error is None
    async with uow:
        await session.execute(
            update(Subscription)
            .where(Subscription.id == case.subscription.id)
            .values(expire_at=datetime_now() + timedelta(minutes=30))
        )
    await _tick_again(case, uow)
    fresh = await case.repository.get(case.subscription.id)
    assert fresh.pending_transaction_id != old_id
    assert (
        await transaction_repository.get_by_id(fresh.pending_transaction_id)
    ).status is TransactionStatus.PAID
    assert len(case.provider.posts) == 2
    assert len(case.provider.keys) == 2
    assert json.loads(case.provider.posts[-1].content)["payment_method_id"] == "fresh-method"


async def test_manual_payment_releases_a_legacy_unknown_pending_order(
    case, transaction_repository, session, uow
) -> None:
    await _lose_recurring_payment(case, session, uow)
    async with uow:
        await case.repository.disable(case.subscription.id, "payment_status_unknown")
    await _manual_renewal(case, transaction_repository, session, uow)
    mandate = await case.repository.get(case.subscription.id)
    assert mandate.pending_transaction_id is None
    assert mandate.enabled and mandate.last_error is None


async def test_worker_repairs_an_already_reenrolled_legacy_mandate(
    case, transaction_repository, session, uow
) -> None:
    old_id = await _lose_recurring_payment(case, session, uow)
    manual = await _manual_renewal(case, transaction_repository, session, uow)
    async with uow:
        await session.execute(
            update(Transaction)
            .where(Transaction.id == old_id)
            .values(status=TransactionStatus.PENDING)
        )
        await session.execute(
            update(RecurringPayment)
            .where(RecurringPayment.subscription_id == case.subscription.id)
            .values(
                pending_transaction_id=old_id,
                enabled=True,
                last_error=None,
                next_attempt_at=datetime_now() - timedelta(seconds=1),
            )
        )
    await case.worker.system()
    repaired = await case.repository.get(case.subscription.id)
    assert repaired.pending_transaction_id is None
    assert repaired.source_transaction_id == manual.id
    assert repaired.enabled and repaired.last_error is None
    assert (await transaction_repository.get_by_id(old_id)).status is TransactionStatus.FAILED
    assert len(case.provider.posts) == 1


async def test_unknown_retirement_rolls_back_the_order_and_mandate_together(
    case, transaction_repository, session, uow
) -> None:
    old_id = await _lose_recurring_payment(case, session, uow)
    with pytest.raises(RuntimeError, match="rollback"):
        async with uow:
            retired = await case.repository.retire_pending(case.subscription.id, old_id)
            assert retired
            raise RuntimeError("rollback")
    mandate = await case.repository.get(case.subscription.id)
    assert mandate.enabled and mandate.pending_transaction_id == old_id
    assert (await transaction_repository.get_by_id(old_id)).status is TransactionStatus.PENDING


async def test_a_paid_order_is_not_retired_while_waiting_for_fulfillment(
    case, transaction_repository, session, uow
) -> None:
    old_id = await _lose_recurring_payment(case, session, uow)
    async with uow:
        await transaction_repository.mark_status(old_id, TransactionStatus.PAID)
    await _tick_again(case, uow)
    mandate = await case.repository.get(case.subscription.id)
    assert mandate.enabled and mandate.pending_transaction_id == old_id
    assert (await transaction_repository.get_by_id(old_id)).status is TransactionStatus.PAID


async def test_manual_reenrollment_keeps_a_known_in_flight_payment(
    case, transaction_repository, session, uow
) -> None:
    case.provider.status = "pending"
    await case.worker.system()
    old = await case.repository.get(case.subscription.id)
    await _manual_renewal(case, transaction_repository, session, uow)
    mandate = await case.repository.get(case.subscription.id)
    assert mandate.pending_transaction_id == old.pending_transaction_id
    await _tick_again(case, uow)
    assert len(case.provider.posts) == 1


async def test_late_success_of_retired_order_cannot_clear_the_new_cycle(
    case,
    transaction_repository,
    gateway_repository,
    user_repository,
    session,
    uow,
) -> None:
    old_id = await _lose_recurring_payment(case, session, uow)
    old = await transaction_repository.get_by_id(old_id)
    provider_id = case.provider.keys[old.idempotency_key]
    await _tick_again(case, uow)
    manual = await _manual_renewal(case, transaction_repository, session, uow)
    async with uow:
        await session.execute(
            update(Subscription)
            .where(Subscription.id == case.subscription.id)
            .values(expire_at=datetime_now() + timedelta(minutes=30))
        )
    case.provider.status = "pending"
    await _tick_again(case, uow)
    active = await case.repository.get(case.subscription.id)
    assert active.pending_transaction_id != old_id
    handler = HandlePaymentWebhookUseCase(
        transaction_repository,
        gateway_repository,
        case.worker._factory,
        user_repository,
        RecordingEventPublisher(),
        uow,
        case.dispatch,
    )
    case.provider.status = "succeeded"
    notification = HandleWebhookDto(
        gateway_type=PaymentGatewayType.YOOKASSA,
        request=WebhookRequest(
            body=json.dumps(
                {
                    "event": "payment.succeeded",
                    "object": {"id": provider_id, "metadata": {"order_ref": old.idempotency_key}},
                }
            ).encode(),
            headers={},
            client_ip="185.71.76.1",
        ),
    )
    await handler.system(notification)
    await handler.system(notification)
    assert (await transaction_repository.get_by_id(old_id)).status is TransactionStatus.PAID
    assert len(case.dispatch.messages) == 1
    async with uow:
        await transaction_repository.mark_fulfilled(old_id, case.subscription.id)
    after = await case.repository.get(case.subscription.id)
    assert after.pending_transaction_id == active.pending_transaction_id
    assert after.source_transaction_id == manual.id
    assert after.enabled


async def test_toggling_preference_cannot_erase_an_unknown_payment(
    case,
    transaction_repository,
    session,
    uow,
) -> None:
    await _lose_recurring_payment(case, session, uow)
    await _tick_again(case, uow)
    disabled = await case.set_state(
        case.user, SetRecurringPaymentDto(subscription_id=case.subscription.id, enabled=False)
    )
    assert disabled.last_error == "payment_status_unknown"
    assert disabled.customer_disabled and not disabled.available
    with pytest.raises(ValidationError):
        await case.set_state(
            case.user, SetRecurringPaymentDto(subscription_id=case.subscription.id, enabled=True)
        )
    await _manual_renewal(case, transaction_repository, session, uow)
    state = await case.get_state(case.user, case.subscription.id)
    assert not state.customer_disabled and state.enabled and state.available


async def test_a_legacy_mandate_without_explicit_consent_is_not_charged(case, session, uow):
    async with uow:
        await session.execute(
            update(RecurringPayment)
            .where(RecurringPayment.subscription_id == case.subscription.id)
            .values(consent_id=None, enabled=True)
        )
    await case.worker.system()
    state = await case.get_state(case.user, case.subscription.id)
    assert not case.provider.posts
    assert not state.enabled and state.available
    assert state.last_error == "consent_required"


async def test_reenabling_requires_fresh_confirmation_of_current_terms(case):
    await case.set_state(
        case.user, SetRecurringPaymentDto(subscription_id=case.subscription.id, enabled=False)
    )
    with pytest.raises(ValidationError):
        await case.set_state(
            case.user, SetRecurringPaymentDto(subscription_id=case.subscription.id, enabled=True)
        )
    assert not (await case.get_state(case.user, case.subscription.id)).enabled


async def test_withdrawal_is_recorded_once_and_reenrollment_has_its_own_record(case, session):
    before = await case.repository.get(case.subscription.id)
    off = SetRecurringPaymentDto(
        subscription_id=case.subscription.id,
        enabled=False,
        channel=PurchaseChannel.BOT,
        event_id="disable-click",
    )
    await case.set_state(case.user, off)
    revoked = await session.get(RecurringConsent, before.consent_id, populate_existing=True)
    assert revoked.revoked_at is not None
    revoked_at = revoked.revoked_at
    assert revoked.revoked_channel == PurchaseChannel.BOT.value
    assert revoked.revoked_event_id == "disable-click"
    await case.set_state(case.user, off)
    await session.refresh(revoked)
    assert revoked.revoked_at == revoked_at
    state = await case.get_state(case.user, case.subscription.id)
    await case.set_state(
        case.user,
        SetRecurringPaymentDto(
            subscription_id=case.subscription.id,
            enabled=True,
            terms_id=state.terms.terms_id,
            channel=PurchaseChannel.BOT,
            event_id="new-consent",
        ),
    )
    after = await case.repository.get(case.subscription.id)
    assert after.enabled and after.consent_id != before.consent_id
    fresh = await session.get(RecurringConsent, after.consent_id)
    assert fresh.event_id == "new-consent" and fresh.revoked_at is None
    assert fresh.terms == state.terms.model_dump(mode="json")


async def test_a_manual_payment_without_consent_does_not_restore_withdrawn_authorization(
    case,
    transaction_repository,
    session,
    uow,
):
    await case.set_state(
        case.user, SetRecurringPaymentDto(subscription_id=case.subscription.id, enabled=False)
    )
    await _manual_renewal(case, transaction_repository, session, uow, consent=False)
    state = await case.get_state(case.user, case.subscription.id)
    assert not state.enabled and state.customer_disabled
    assert (await case.repository.get(case.subscription.id)).consent_id is None


async def test_a_new_policy_requires_new_consent_even_if_the_saved_method_works(case):
    case.worker._config.recurring.lead_minutes += 1
    await case.worker.system()
    state = await case.get_state(case.user, case.subscription.id)
    assert not state.enabled and state.last_error == "consent_required"
    assert not case.provider.posts


async def test_an_ambiguous_request_is_not_retried_beyond_the_agreed_overdue_window(
    case,
    session,
    uow,
):
    case.provider.lose_response = True
    await case.worker.system()
    async with uow:
        await session.execute(
            update(Subscription)
            .where(Subscription.id == case.subscription.id)
            .values(expire_at=datetime_now() - timedelta(hours=25))
        )
    await _tick_again(case, uow)
    assert len(case.provider.posts) == 1
    assert not (await case.repository.get(case.subscription.id)).enabled


async def test_account_merge_keeps_consent_history_but_requires_new_authorization(
    case,
    user_repository,
    session,
    uow,
):
    original = await case.repository.get(case.subscription.id)
    async with uow:
        target = await user_repository.create(CreateUserDto(name="merged customer"))
        await AccountMergeRepository(session).reassign(case.user.id, target.id, {})
    await case.worker.system()
    mandate = await case.repository.get(case.subscription.id)
    assert not mandate.enabled and mandate.last_error == "consent_required"
    assert not case.provider.posts
    consent = await session.get(RecurringConsent, original.consent_id, populate_existing=True)
    assert consent.user_id == case.user.id
    assert consent.terms["user_id"] == case.user.id
