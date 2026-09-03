from datetime import timedelta
from decimal import Decimal
from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import setup_dishka
from sqlalchemy.ext.asyncio import AsyncSession

import app.modules.payments.usecases.handle_yookassa_webhook as webhook_usecase_module
from app.api.app import get_app
from app.core.config import AppConfig
from app.core.di.providers import get_core_providers
from app.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PaymentOrderStatus,
    PurchaseType,
)
from app.core.utils.time import datetime_now
from app.modules.api_tokens import get_api_tokens_providers
from app.modules.auth import get_auth_providers
from app.modules.gateways import get_gateways_providers
from app.modules.payments.dto import CreatePaymentOrderDto
from app.modules.payments.repository import PaymentOrderRepository
from app.modules.payments.usecases.handle_yookassa_webhook import HandleYooKassaWebhookUseCase
from app.modules.plans import get_plans_providers
from app.modules.referrals import get_referrals_providers
from app.modules.settings import get_settings_providers
from app.modules.subscriptions import SubscriptionRepository
from app.modules.translations import get_translations_providers
from app.modules.users import get_users_providers
from tests.modules.subscriptions.factories import make_plan_snapshot


class _TestSessionProvider(Provider):
    scope = Scope.REQUEST

    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self._session = session

    @provide
    def get_session(self) -> AsyncSession:
        return self._session


class _PaymentsProvider(Provider):
    scope = Scope.REQUEST

    payment_order_repository = provide(PaymentOrderRepository)
    subscription_repository = provide(SubscriptionRepository)
    handle_yookassa_webhook_use_case = provide(HandleYooKassaWebhookUseCase)


@pytest.fixture
async def test_container(session: AsyncSession, config: AppConfig) -> AsyncIterator[AsyncContainer]:
    providers = [
        *get_core_providers(),
        *get_users_providers(),
        *get_auth_providers(),
        *get_api_tokens_providers(),
        *get_plans_providers(),
        *get_referrals_providers(),
        *get_gateways_providers(),
        *get_settings_providers(),
        *get_translations_providers(),
        _PaymentsProvider(),
        _TestSessionProvider(session),
    ]
    container = make_async_container(*providers, context={AppConfig: config})
    yield container
    await container.close()


@pytest.fixture
async def client(
    config: AppConfig, test_container: AsyncContainer
) -> AsyncIterator[httpx.AsyncClient]:
    app = get_app(config)
    setup_dishka(test_container, app)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


def _pending_order_dto(
    *, user_id: int, plan_id: int, idempotency_key: str
) -> CreatePaymentOrderDto:
    return CreatePaymentOrderDto(
        user_id=user_id,
        plan_id=plan_id,
        plan_snapshot=make_plan_snapshot(plan_id=plan_id),
        duration_days=30,
        currency=Currency.RUB,
        purchase_type=PurchaseType.NEW,
        target_subscription_id=None,
        gateway_type=PaymentGatewayType.YOOKASSA,
        base_price=Decimal("500"),
        discount_percent=0,
        discount_source=DiscountSource.NONE,
        final_price=Decimal("500"),
        customer_email=None,
        idempotency_key=idempotency_key,
        expires_at=datetime_now() + timedelta(minutes=30),
    )


async def test_webhook_order_not_found_returns_200(client) -> None:
    response = await client.post(
        "/api/v1/payments/webhooks/yookassa",
        json={"event": "payment.succeeded", "object": {"id": "unknown-id"}},
    )
    assert response.status_code == 200


async def test_webhook_already_paid_order_is_a_noop_and_never_calls_verify(
    client, payment_order_repository, uow, user_id, plan_id, monkeypatch
) -> None:
    async with uow:
        order = await payment_order_repository.create(
            _pending_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="wh-key-1")
        )
        await payment_order_repository.mark_status(
            order.id, PaymentOrderStatus.PAID, external_payment_id="yk-1"
        )

    class _RaisingGateway:
        async def verify_payment(self, external_payment_id: str, settings: dict[str, str]) -> bool:
            raise AssertionError("verify_payment must not be called for a terminal-status order")

    monkeypatch.setattr(webhook_usecase_module, "YooKassaGateway", _RaisingGateway)

    response = await client.post(
        "/api/v1/payments/webhooks/yookassa",
        json={"event": "payment.succeeded", "object": {"id": "yk-1"}},
    )
    assert response.status_code == 200


async def test_webhook_verified_success_marks_paid_and_dispatches_purchase(
    client, payment_order_repository, uow, user_id, plan_id, monkeypatch
) -> None:
    async with uow:
        order = await payment_order_repository.create(
            _pending_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="wh-key-2")
        )
        await payment_order_repository.mark_status(
            order.id, PaymentOrderStatus.PENDING, external_payment_id="yk-2"
        )

    class _VerifyingGateway:
        async def verify_payment(self, external_payment_id: str, settings: dict[str, str]) -> bool:
            return True

    monkeypatch.setattr(webhook_usecase_module, "YooKassaGateway", _VerifyingGateway)

    dispatched: list[dict[str, object]] = []

    async def _fake_kiq(**kwargs: object) -> None:
        dispatched.append(kwargs)

    monkeypatch.setattr(webhook_usecase_module.purchase_subscription_task, "kiq", _fake_kiq)

    response = await client.post(
        "/api/v1/payments/webhooks/yookassa",
        json={"event": "payment.succeeded", "object": {"id": "yk-2"}},
    )

    assert response.status_code == 200
    fetched = await payment_order_repository.get_by_id(order.id)
    assert fetched.status is PaymentOrderStatus.PAID
    assert len(dispatched) == 1
    assert dispatched[0]["idempotency_key"] == "wh-key-2"


async def test_webhook_unverified_payment_leaves_the_order_pending_and_dispatches_nothing(
    client, payment_order_repository, uow, user_id, plan_id, monkeypatch
) -> None:
    async with uow:
        order = await payment_order_repository.create(
            _pending_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="wh-key-4")
        )
        await payment_order_repository.mark_status(
            order.id, PaymentOrderStatus.PENDING, external_payment_id="yk-4"
        )

    class _DenyingGateway:
        async def verify_payment(self, external_payment_id: str, settings: dict[str, str]) -> bool:
            return False

    monkeypatch.setattr(webhook_usecase_module, "YooKassaGateway", _DenyingGateway)

    dispatched: list[dict[str, object]] = []

    async def _fake_kiq(**kwargs: object) -> None:
        dispatched.append(kwargs)

    monkeypatch.setattr(webhook_usecase_module.purchase_subscription_task, "kiq", _fake_kiq)

    response = await client.post(
        "/api/v1/payments/webhooks/yookassa",
        json={"event": "payment.succeeded", "object": {"id": "yk-4"}},
    )

    assert response.status_code == 200
    fetched = await payment_order_repository.get_by_id(order.id)
    assert fetched.status is PaymentOrderStatus.PENDING
    assert dispatched == []


async def test_webhook_malformed_body_without_object_id_returns_400(client) -> None:
    response = await client.post(
        "/api/v1/payments/webhooks/yookassa", json={"event": "payment.succeeded"}
    )

    assert response.status_code == 400


async def test_webhook_gateway_exception_returns_502(
    client, payment_order_repository, uow, user_id, plan_id, monkeypatch
) -> None:
    async with uow:
        order = await payment_order_repository.create(
            _pending_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="wh-key-3")
        )
        await payment_order_repository.mark_status(
            order.id, PaymentOrderStatus.PENDING, external_payment_id="yk-3"
        )

    class _FailingGateway:
        async def verify_payment(self, external_payment_id: str, settings: dict[str, str]) -> bool:
            raise ConnectionError("simulated network failure")

    monkeypatch.setattr(webhook_usecase_module, "YooKassaGateway", _FailingGateway)

    response = await client.post(
        "/api/v1/payments/webhooks/yookassa",
        json={"event": "payment.succeeded", "object": {"id": "yk-3"}},
    )

    assert response.status_code == 502
