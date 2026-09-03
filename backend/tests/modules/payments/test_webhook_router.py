from datetime import timedelta
from decimal import Decimal
from typing import AsyncIterator, Optional

import httpx
import pytest
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import setup_dishka
from sqlalchemy.ext.asyncio import AsyncSession

import app.modules.payments.usecases.handle_payment_webhook as webhook_usecase_module
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
from app.modules.blacklist import get_blacklist_providers
from app.modules.gateways import get_gateways_providers
from app.modules.payments.dto import CreatePaymentOrderDto
from app.modules.payments.gateways.base import WebhookResult
from app.modules.payments.gateways.factory import PaymentGatewayFactory
from app.modules.payments.repository import PaymentOrderRepository
from app.modules.payments.usecases.handle_payment_webhook import HandlePaymentWebhookUseCase
from app.modules.plans import get_plans_providers
from app.modules.referrals import get_referrals_providers
from app.modules.settings import get_settings_providers
from app.modules.subscriptions import SubscriptionRepository
from app.modules.translations import get_translations_providers
from app.modules.users import get_users_providers
from tests.modules.subscriptions.factories import make_plan_snapshot


class _StubGateway:
    def __init__(
        self,
        *,
        parse_result: Optional[WebhookResult],
        verify_result: bool = True,
        verify_exc: Optional[BaseException] = None,
    ) -> None:
        self._parse_result = parse_result
        self._verify_result = verify_result
        self._verify_exc = verify_exc

    async def parse_webhook(self, request: object) -> Optional[WebhookResult]:
        return self._parse_result

    async def verify_payment(self, order: object) -> bool:
        if self._verify_exc is not None:
            raise self._verify_exc
        return self._verify_result

    def webhook_ack(self, result: object) -> str:
        return ""


def _install_stub(monkeypatch: pytest.MonkeyPatch, stub: _StubGateway) -> None:
    monkeypatch.setattr(
        "app.modules.payments.gateways.factory.PaymentGatewayFactory.build",
        lambda self, gateway_type, settings: stub,
    )


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
    handle_payment_webhook_use_case = provide(HandlePaymentWebhookUseCase)
    payment_gateway_factory = provide(PaymentGatewayFactory, scope=Scope.APP)


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
        *get_blacklist_providers(),
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


async def test_unknown_gateway_type_returns_404(client) -> None:
    response = await client.post("/api/v1/payments/not-a-gateway", content=b"{}")
    assert response.status_code == 404


async def test_gateway_type_with_no_adapter_returns_404(client) -> None:
    # Real PaymentGatewayFactory.build (not the stub) -- CRYPTOMUS is a valid
    # enum value but has no entry in GATEWAY_REGISTRY.
    response = await client.post("/api/v1/payments/cryptomus", content=b"{}")
    assert response.status_code == 404


async def test_webhook_order_not_found_returns_200(client, monkeypatch) -> None:
    _install_stub(
        monkeypatch,
        _StubGateway(
            parse_result=WebhookResult(reference="missing", status=PaymentOrderStatus.PAID)
        ),
    )
    response = await client.post("/api/v1/payments/yookassa", content=b"{}")
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

    _install_stub(
        monkeypatch,
        _StubGateway(
            parse_result=WebhookResult(reference="wh-key-1", status=PaymentOrderStatus.PAID),
            verify_exc=AssertionError("verify_payment must not be called for a terminal order"),
        ),
    )

    response = await client.post("/api/v1/payments/yookassa", content=b"{}")
    assert response.status_code == 200


async def test_webhook_verified_success_marks_paid_and_dispatches_purchase(
    client, payment_order_repository, uow, user_id, plan_id, monkeypatch
) -> None:
    async with uow:
        order = await payment_order_repository.create(
            _pending_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="wh-key-2")
        )

    _install_stub(
        monkeypatch,
        _StubGateway(
            parse_result=WebhookResult(
                reference="wh-key-2",
                status=PaymentOrderStatus.PAID,
                provider_payment_id="yk-2",
            )
        ),
    )

    dispatched: list[dict[str, object]] = []

    async def _fake_kiq(**kwargs: object) -> None:
        dispatched.append(kwargs)

    monkeypatch.setattr(webhook_usecase_module.purchase_subscription_task, "kiq", _fake_kiq)

    response = await client.post("/api/v1/payments/yookassa", content=b"{}")

    assert response.status_code == 200
    fetched = await payment_order_repository.get_by_id(order.id)
    assert fetched.status is PaymentOrderStatus.PAID
    assert fetched.external_payment_id == "yk-2"
    assert len(dispatched) == 1
    assert dispatched[0]["idempotency_key"] == "wh-key-2"


async def test_webhook_unverified_payment_leaves_the_order_pending_and_dispatches_nothing(
    client, payment_order_repository, uow, user_id, plan_id, monkeypatch
) -> None:
    async with uow:
        order = await payment_order_repository.create(
            _pending_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="wh-key-4")
        )

    _install_stub(
        monkeypatch,
        _StubGateway(
            parse_result=WebhookResult(reference="wh-key-4", status=PaymentOrderStatus.PAID),
            verify_result=False,
        ),
    )

    dispatched: list[dict[str, object]] = []

    async def _fake_kiq(**kwargs: object) -> None:
        dispatched.append(kwargs)

    monkeypatch.setattr(webhook_usecase_module.purchase_subscription_task, "kiq", _fake_kiq)

    response = await client.post("/api/v1/payments/yookassa", content=b"{}")

    assert response.status_code == 200
    fetched = await payment_order_repository.get_by_id(order.id)
    assert fetched.status is PaymentOrderStatus.PENDING
    assert dispatched == []


async def test_webhook_gateway_exception_returns_502(
    client, payment_order_repository, uow, user_id, plan_id, monkeypatch
) -> None:
    async with uow:
        await payment_order_repository.create(
            _pending_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="wh-key-3")
        )

    _install_stub(
        monkeypatch,
        _StubGateway(
            parse_result=WebhookResult(reference="wh-key-3", status=PaymentOrderStatus.PAID),
            verify_exc=ConnectionError("simulated network failure"),
        ),
    )

    response = await client.post("/api/v1/payments/yookassa", content=b"{}")
    assert response.status_code == 502
