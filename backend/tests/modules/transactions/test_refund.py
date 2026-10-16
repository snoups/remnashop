from collections.abc import Awaitable, Callable, Iterator
from datetime import timedelta
from decimal import Decimal
from typing import Any, Optional

import pytest
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy import update

from app.core.db.models.bot_settings import BotSettings
from app.core.db.models.transaction import Transaction
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PurchaseType,
    Role,
    TransactionStatus,
)
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError, PaymentGatewayError
from app.core.utils.lock import cron_lock
from app.core.utils.time import datetime_now
from app.modules.gateways.repository import GatewayRepository
from app.modules.settings import SettingsRepository
from app.modules.settings.dto import UpdateBotSettingsDto
from app.modules.subscriptions import PurchaseRollbackDto, RollbackPreviewDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.transactions.dto import CreateTransactionDto, RefundTransactionDto, TransactionDto
from app.modules.transactions.events import (
    TransactionRefundedEvent,
    TransactionRefundedManuallyEvent,
)
from app.modules.transactions.gateways.factory import PaymentGatewayFactory
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.usecases import PreviewRefundUseCase, RefundTransactionUseCase
from app.modules.users import UserRepository
from app.modules.users.dto import CreateUserDto, UserDto
from tests.fakes.events import RecordingEventPublisher
from tests.modules.subscriptions.factories import create_subscription, make_plan_snapshot

_AVAILABLE = RollbackPreviewDto(available=True, blocked_reason=None, old_term_expired=False)


class _FakeStarsGateway:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.refunds: list[tuple[str, int]] = []
        self.error: Optional[Exception] = None
        self.on_refund: Optional[Callable[[], Awaitable[None]]] = None

    async def refund(self, charge_id: str, telegram_id: int) -> None:
        self.calls.append("refund")
        if self.on_refund is not None:
            await self.on_refund()
        if self.error is not None:
            raise self.error
        self.refunds.append((charge_id, telegram_id))


class _FakeFactory(PaymentGatewayFactory):
    def __init__(self, gateway: _FakeStarsGateway) -> None:
        self._gateway = gateway

    def build(self, gateway_type, settings):  # type: ignore[no-untyped-def]
        self.settings = settings
        return self._gateway  # type: ignore[return-value]


class _StubPreview:
    def __init__(self) -> None:
        self.result = _AVAILABLE
        self.inputs: list[PurchaseRollbackDto] = []

    async def __call__(self, data: PurchaseRollbackDto) -> RollbackPreviewDto:
        self.inputs.append(data)
        return self.result


class _StubRollback:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.inputs: list[PurchaseRollbackDto] = []
        self.error: Optional[Exception] = None

    async def __call__(self, actor: Any, data: PurchaseRollbackDto) -> None:
        self.calls.append("rollback")
        self.inputs.append(data)
        if self.error is not None:
            raise self.error


class _StubRollbackService:
    def __init__(self, preview: _StubPreview, rollback: _StubRollback) -> None:
        self.preview = preview
        self.rollback = rollback


@pytest.fixture
def calls() -> list[str]:
    return []


@pytest.fixture
def gateway(calls: list[str]) -> _FakeStarsGateway:
    return _FakeStarsGateway(calls)


@pytest.fixture
def preview_rollback() -> _StubPreview:
    return _StubPreview()


@pytest.fixture
def rollback(calls: list[str]) -> _StubRollback:
    return _StubRollback(calls)


@pytest.fixture
def events() -> RecordingEventPublisher:
    return RecordingEventPublisher()


@pytest.fixture
async def owner(user_repository: UserRepository) -> UserDto:
    return await user_repository.create(CreateUserDto(name="refund-owner", role=Role.OWNER))


@pytest.fixture
async def buyer(user_repository: UserRepository) -> UserDto:
    return await user_repository.create(CreateUserDto(name="refund-buyer", telegram_id=810_001))


@pytest.fixture(autouse=True)
async def _bot(settings_repository: SettingsRepository, uow: UnitOfWork) -> None:
    async with uow:
        await settings_repository.update_bot_settings(UpdateBotSettingsDto(token="123:abc"))


@pytest.fixture
def refund(
    transaction_repository: TransactionRepository,
    user_repository: UserRepository,
    gateway_repository: GatewayRepository,
    settings_repository: SettingsRepository,
    gateway: _FakeStarsGateway,
    preview_rollback: _StubPreview,
    rollback: _StubRollback,
    events: RecordingEventPublisher,
    uow: UnitOfWork,
    redis: Redis,
) -> RefundTransactionUseCase:
    return RefundTransactionUseCase(
        transaction_repository,
        user_repository,
        gateway_repository,
        settings_repository,
        _FakeFactory(gateway),
        _StubRollbackService(preview_rollback, rollback),  # type: ignore[arg-type]
        events,
        uow,
        redis,
    )


@pytest.fixture
def preview(
    transaction_repository: TransactionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    preview_rollback: _StubPreview,
    rollback: _StubRollback,
    uow: UnitOfWork,
) -> PreviewRefundUseCase:
    return PreviewRefundUseCase(
        transaction_repository,
        user_repository,
        settings_repository,
        _StubRollbackService(preview_rollback, rollback),  # type: ignore[arg-type]
        uow,
    )


async def _order(
    transaction_repository: TransactionRepository,
    uow: UnitOfWork,
    *,
    user_id: int,
    plan_id: int,
    key: str = "refund-order",
    gateway_type: PaymentGatewayType = PaymentGatewayType.TELEGRAM_STARS,
    status: TransactionStatus = TransactionStatus.PAID,
    charge_id: Optional[str] = "charge-1",
    purchase_type: PurchaseType = PurchaseType.NEW,
    target_subscription_id: Optional[int] = None,
    is_test: bool = False,
) -> TransactionDto:
    async with uow:
        created = await transaction_repository.create(
            CreateTransactionDto(
                user_id=user_id,
                plan_id=plan_id,
                plan_snapshot=make_plan_snapshot(plan_id=plan_id),
                duration_days=30,
                currency=Currency.XTR,
                purchase_type=purchase_type,
                target_subscription_id=target_subscription_id,
                gateway_type=gateway_type,
                base_price=Decimal("50"),
                discount_percent=0,
                discount_source=DiscountSource.NONE,
                final_price=Decimal("50"),
                anchor_base_price=Decimal("50"),
                anchor_final_price=Decimal("50"),
                customer_email=None,
                idempotency_key=key,
                is_test=is_test,
                expires_at=datetime_now() + timedelta(minutes=30),
            )
        )
        return await transaction_repository.mark_status(
            created.id, status, external_payment_id=charge_id
        )


@pytest.fixture
async def paid_stars_order(
    transaction_repository: TransactionRepository, uow: UnitOfWork, buyer: UserDto, plan_id: int
) -> TransactionDto:
    return await _order(transaction_repository, uow, user_id=buyer.id, plan_id=plan_id)


def _input(order: TransactionDto, rollback_subscription: bool = False) -> RefundTransactionDto:
    return RefundTransactionDto(
        transaction_id=order.id, rollback_subscription=rollback_subscription, client_ip="10.0.0.1"
    )


async def test_refund_marks_refunded_and_publishes(
    refund: RefundTransactionUseCase,
    paid_stars_order: TransactionDto,
    owner: UserDto,
    buyer: UserDto,
    gateway: _FakeStarsGateway,
    events: RecordingEventPublisher,
) -> None:
    result = await refund(owner, _input(paid_stars_order))

    assert result.transaction.order.status is TransactionStatus.REFUNDED
    assert result.rollback_failed is False
    assert gateway.refunds == [("charge-1", 810_001)]
    refunded, manual = events.events
    assert isinstance(refunded, TransactionRefundedEvent)
    assert refunded.order_id == paid_stars_order.id
    assert isinstance(manual, TransactionRefundedManuallyEvent)
    assert manual.target.id == buyer.id
    assert manual.ip_address == "10.0.0.1"
    assert manual.rollback_subscription is False


async def test_refund_refused_by_telegram_changes_nothing(
    refund: RefundTransactionUseCase,
    paid_stars_order: TransactionDto,
    owner: UserDto,
    gateway: _FakeStarsGateway,
    events: RecordingEventPublisher,
    transaction_repository: TransactionRepository,
    uow: UnitOfWork,
) -> None:
    gateway.error = PaymentGatewayError("refundStarPayment refused: CHARGE_NOT_FOUND")

    with pytest.raises(PaymentGatewayError):
        await refund(owner, _input(paid_stars_order))

    async with uow:
        order = await transaction_repository.get_by_id(paid_stars_order.id)
    assert order.status is TransactionStatus.PAID
    assert events.events == []


@pytest.fixture
def errors() -> Iterator[list[str]]:
    messages: list[str] = []
    sink = logger.add(lambda message: messages.append(str(message)), level="ERROR")
    yield messages
    logger.remove(sink)


async def test_refund_wraps_a_raw_transport_error(
    refund: RefundTransactionUseCase,
    paid_stars_order: TransactionDto,
    owner: UserDto,
    gateway: _FakeStarsGateway,
    errors: list[str],
) -> None:
    gateway.error = RuntimeError("https://api.telegram.org/bot123:abc/refundStarPayment")

    with pytest.raises(PaymentGatewayError) as error:
        await refund(owner, _input(paid_stars_order))

    assert "123:abc" not in str(error.value)
    (logged,) = errors
    assert "refund outcome unknown" in logged
    assert "RuntimeError" in logged
    assert "123:abc" not in logged


async def test_refund_retry_completes_after_a_failed_record(
    refund: RefundTransactionUseCase,
    paid_stars_order: TransactionDto,
    owner: UserDto,
    gateway: _FakeStarsGateway,
    events: RecordingEventPublisher,
    transaction_repository: TransactionRepository,
    monkeypatch: pytest.MonkeyPatch,
    errors: list[str],
) -> None:
    mark_status_if = transaction_repository.mark_status_if
    failures = [RuntimeError("db down")]

    async def flaky_mark_status_if(*args: Any, **kwargs: Any) -> bool:
        if failures:
            raise failures.pop()
        return await mark_status_if(*args, **kwargs)

    monkeypatch.setattr(transaction_repository, "mark_status_if", flaky_mark_status_if)

    with pytest.raises(RuntimeError):
        await refund(owner, _input(paid_stars_order))
    assert any("not recorded" in message for message in errors)
    assert events.events == []

    # the gateway reports an already refunded charge as done
    result = await refund(owner, _input(paid_stars_order))

    assert result.transaction.order.status is TransactionStatus.REFUNDED
    assert len(gateway.refunds) == 2
    refunded, manual = events.events
    assert isinstance(refunded, TransactionRefundedEvent)
    assert isinstance(manual, TransactionRefundedManuallyEvent)


@pytest.mark.parametrize("variant", ["refunded", "not_stars", "test", "no_charge", "no_telegram"])
async def test_refund_rejects_a_non_refundable_order(
    variant: str,
    refund: RefundTransactionUseCase,
    owner: UserDto,
    buyer: UserDto,
    gateway: _FakeStarsGateway,
    transaction_repository: TransactionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    user_id = buyer.id
    kwargs: dict[str, Any] = {}
    if variant == "refunded":
        kwargs["status"] = TransactionStatus.REFUNDED
    elif variant == "not_stars":
        kwargs["gateway_type"] = PaymentGatewayType.YOOKASSA
    elif variant == "test":
        kwargs["is_test"] = True
    elif variant == "no_charge":
        kwargs["charge_id"] = None
    elif variant == "no_telegram":
        user_id = (await user_repository.create(CreateUserDto(name="no-tg"))).id
    order = await _order(transaction_repository, uow, user_id=user_id, plan_id=plan_id, **kwargs)
    with pytest.raises(ConflictError) as error:
        await refund(owner, _input(order))

    assert error.value.code is ErrorCode.TRANSACTION_NOT_REFUNDABLE
    assert gateway.refunds == []


async def test_refund_with_rollback_calls_rollback_after_refund(
    refund: RefundTransactionUseCase,
    paid_stars_order: TransactionDto,
    owner: UserDto,
    calls: list[str],
    rollback: _StubRollback,
) -> None:
    result = await refund(owner, _input(paid_stars_order, rollback_subscription=True))

    assert calls == ["refund", "rollback"]
    assert result.rollback_failed is False
    assert rollback.inputs[0].currency is Currency.XTR
    assert rollback.inputs[0].price_paid == Decimal("50")


async def test_refund_blocked_rollback_is_refused_before_refunding(
    refund: RefundTransactionUseCase,
    paid_stars_order: TransactionDto,
    owner: UserDto,
    gateway: _FakeStarsGateway,
    preview_rollback: _StubPreview,
) -> None:
    preview_rollback.result = RollbackPreviewDto(
        available=False, blocked_reason="subscription_deleted", old_term_expired=False
    )

    with pytest.raises(ConflictError) as error:
        await refund(owner, _input(paid_stars_order, rollback_subscription=True))

    assert error.value.code is ErrorCode.SUBSCRIPTION_ROLLBACK_BLOCKED
    assert gateway.refunds == []


async def test_rollback_failure_keeps_refund(
    refund: RefundTransactionUseCase,
    paid_stars_order: TransactionDto,
    owner: UserDto,
    rollback: _StubRollback,
) -> None:
    rollback.error = RuntimeError("panel down")

    result = await refund(owner, _input(paid_stars_order, rollback_subscription=True))

    assert result.rollback_failed is True
    assert result.transaction.order.status is TransactionStatus.REFUNDED


async def test_refund_holds_a_lock_against_a_parallel_click(
    refund: RefundTransactionUseCase,
    paid_stars_order: TransactionDto,
    owner: UserDto,
    gateway: _FakeStarsGateway,
    redis: Redis,
) -> None:
    async with cron_lock(redis, f"refund:{paid_stars_order.id}", ttl_seconds=60) as acquired:
        assert acquired
        with pytest.raises(ConflictError) as error:
            await refund(owner, _input(paid_stars_order))

    assert error.value.code is ErrorCode.TRANSACTION_NOT_REFUNDABLE
    assert gateway.refunds == []


async def test_preview_reports_reason_and_rollback(
    preview: PreviewRefundUseCase,
    preview_rollback: _StubPreview,
    owner: UserDto,
    buyer: UserDto,
    transaction_repository: TransactionRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    pending = await _order(
        transaction_repository,
        uow,
        user_id=buyer.id,
        plan_id=plan_id,
        key="preview-pending",
        charge_id="preview-pending",
        status=TransactionStatus.PENDING,
    )
    unprovisioned = await _order(
        transaction_repository,
        uow,
        user_id=buyer.id,
        plan_id=plan_id,
        key="preview-bare",
        charge_id="preview-bare",
    )
    async with uow:
        subscription = await create_subscription(
            subscription_repository, user_repository, telegram_id=810_002, remnawave_user_id=81
        )
    provisioned = await _order(
        transaction_repository,
        uow,
        user_id=buyer.id,
        plan_id=plan_id,
        key="preview-provisioned",
        charge_id="preview-provisioned",
    )
    async with uow:
        await transaction_repository.mark_fulfilled(provisioned.id, subscription.id)
        # the test shares one DB transaction, so now() is the same for every row
        await transaction_repository.session.execute(
            update(Transaction)
            .where(Transaction.id == provisioned.id)
            .values(created_at=datetime_now() - timedelta(hours=1))
        )
    await _order(
        transaction_repository,
        uow,
        user_id=buyer.id,
        plan_id=plan_id,
        key="preview-later",
        charge_id="preview-later",
        purchase_type=PurchaseType.RENEW,
        target_subscription_id=subscription.id,
    )

    not_paid = await preview(owner, pending.id)
    bare = await preview(owner, unprovisioned.id)
    full = await preview(owner, provisioned.id)

    assert not_paid.refundable is False
    assert not_paid.reason == "not_paid"
    assert not_paid.rollback is None
    assert bare.refundable is True
    assert bare.rollback == _AVAILABLE
    assert preview_rollback.inputs[0].fulfilled_subscription_id is None
    assert full.rollback == _AVAILABLE
    assert preview_rollback.inputs[-1].fulfilled_subscription_id == subscription.id
    assert preview_rollback.inputs[-1].has_later_paid_order is True


async def _clear_bot_token(transaction_repository: TransactionRepository, uow: UnitOfWork) -> None:
    async with uow:
        await transaction_repository.session.execute(update(BotSettings).values(token=None))


async def test_preview_and_refund_refuse_without_a_bot(
    preview: PreviewRefundUseCase,
    refund: RefundTransactionUseCase,
    paid_stars_order: TransactionDto,
    owner: UserDto,
    gateway: _FakeStarsGateway,
    transaction_repository: TransactionRepository,
    uow: UnitOfWork,
) -> None:
    await _clear_bot_token(transaction_repository, uow)

    result = await preview(owner, paid_stars_order.id)
    with pytest.raises(ConflictError) as error:
        await refund(owner, _input(paid_stars_order))

    assert result.refundable is False
    assert result.reason == "bot_not_configured"
    assert error.value.code is ErrorCode.TRANSACTION_NOT_REFUNDABLE
    assert gateway.refunds == []


async def test_rollback_sees_an_order_paid_during_the_refund(
    refund: RefundTransactionUseCase,
    owner: UserDto,
    buyer: UserDto,
    gateway: _FakeStarsGateway,
    rollback: _StubRollback,
    transaction_repository: TransactionRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    async with uow:
        subscription = await create_subscription(
            subscription_repository, user_repository, telegram_id=810_003, remnawave_user_id=82
        )
    order = await _order(transaction_repository, uow, user_id=buyer.id, plan_id=plan_id)
    async with uow:
        await transaction_repository.mark_fulfilled(order.id, subscription.id)
        await transaction_repository.session.execute(
            update(Transaction)
            .where(Transaction.id == order.id)
            .values(created_at=datetime_now() - timedelta(hours=1))
        )

    async def renew_meanwhile() -> None:
        await _order(
            transaction_repository,
            uow,
            user_id=buyer.id,
            plan_id=plan_id,
            key="refund-later",
            charge_id="refund-later",
            purchase_type=PurchaseType.RENEW,
            target_subscription_id=subscription.id,
        )

    gateway.on_refund = renew_meanwhile

    await refund(owner, _input(order, rollback_subscription=True))

    assert rollback.inputs[0].has_later_paid_order is True
