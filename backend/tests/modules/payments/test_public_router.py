import datetime
from datetime import timedelta, timezone
from decimal import Decimal
from typing import AsyncIterator
from uuid import uuid4

import httpx
import pytest
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import setup_dishka
from sqlalchemy.ext.asyncio import AsyncSession

import app.modules.payments.gateways.yookassa as yookassa_module
from app.api.app import get_app
from app.core.config import AppConfig
from app.core.constants import API_V1
from app.core.db.uow import UnitOfWork
from app.core.di.providers import get_core_providers
from app.core.enums import Locale, PaymentGatewayType, PlanType, Role
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.modules.api_tokens import get_api_tokens_providers
from app.modules.auth import get_auth_providers
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.blacklist import get_blacklist_providers
from app.modules.gateways import GatewaysRepository, get_gateways_providers
from app.modules.payments.gateways.factory import PaymentGatewayFactory
from app.modules.payments.repository import PaymentOrderRepository
from app.modules.payments.usecases.create_checkout import CreateCheckoutUseCase
from app.modules.plans import get_plans_providers
from app.modules.plans.dto import (
    CreatePlanDto,
    PlanDto,
    SetPlanDurationDto,
    SetPlanDurationsDto,
    UpdatePlanDto,
    UpdatePlanSquadsDto,
)
from app.modules.plans.repository import PlanRepository
from app.modules.pricing import get_pricing_providers
from app.modules.referrals import get_referrals_providers
from app.modules.settings import get_settings_providers
from app.modules.subscriptions import get_subscriptions_providers
from app.modules.translations import get_translations_providers
from app.modules.users import get_users_providers
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


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
    create_checkout_use_case = provide(CreateCheckoutUseCase)
    payment_gateway_factory = provide(PaymentGatewayFactory, scope=Scope.APP)


@pytest.fixture
async def test_container(session: AsyncSession, config: AppConfig) -> AsyncIterator[AsyncContainer]:
    providers = [
        *get_core_providers(),
        *get_users_providers(),
        *get_auth_providers(),
        *get_api_tokens_providers(),
        *get_plans_providers(),
        *get_pricing_providers(),
        *get_referrals_providers(),
        *get_gateways_providers(),
        *get_settings_providers(),
        *get_subscriptions_providers(),
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


async def _auth_headers(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> dict[str, str]:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(
                login="checkoutrouter",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name="checkoutrouter",
                role=Role.USER,
                language=Locale.EN,
            )
        )
        await uow.commit()
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token("test-refresh-token-checkout"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
        )
    )
    token = create_access_token(user.id, session.id, config.jwt_secret.get_secret_value())
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def auth_headers(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> dict[str, str]:
    return await _auth_headers(user_repository, session_repository, uow, config)


@pytest.fixture
async def plan(plan_repository: PlanRepository) -> PlanDto:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="checkout-router-plan",
            name="Checkout Router Plan",
            type=PlanType.BOTH,
            traffic_limit=100,
            device_limit=3,
        )
    )
    await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=created.id,
            durations=[SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("500.00"))],
        )
    )
    await plan_repository.update_squads(
        UpdatePlanSquadsDto(plan_id=created.id, internal_squads=[uuid4()], external_squad=None)
    )
    return await plan_repository.update(UpdatePlanDto(plan_id=created.id, is_active=True))


def _patch_yookassa_transport(
    monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport
) -> None:
    # The gateway reuses one module-level client rather than constructing one
    # per call -- swap that instance out for the duration of the test instead
    # of patching the AsyncClient constructor.
    monkeypatch.setattr(yookassa_module, "http_client", httpx.AsyncClient(transport=handler))


async def test_checkout_returns_confirmation_url_for_a_valid_plan(
    client: httpx.AsyncClient,
    plan: PlanDto,
    auth_headers: dict[str, str],
    gateways_repository: GatewaysRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await gateways_repository.update_settings(
        PaymentGatewayType.YOOKASSA, {"shop_id": "1000", "api_key": "test_key"}
    )
    await gateways_repository.set_active(PaymentGatewayType.YOOKASSA, True)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "yk-payment-router-1",
                "confirmation": {"confirmation_url": "https://yookassa.ru/pay/router-1"},
            },
        )

    _patch_yookassa_transport(monkeypatch, httpx.MockTransport(handler))

    response = await client.post(
        f"{API_V1}/payments/checkout",
        json={
            "plan_id": plan.id,
            "duration_days": 30,
            "currency": "RUB",
            "purchase_type": "NEW",
            "gateway_type": "YOOKASSA",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["confirmation_url"] == "https://yookassa.ru/pay/router-1"


async def test_checkout_rejects_a_currency_the_gateway_does_not_settle(
    client: httpx.AsyncClient, plan: PlanDto, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        f"{API_V1}/payments/checkout",
        json={
            "plan_id": plan.id,
            "duration_days": 30,
            "currency": "USD",
            "purchase_type": "NEW",
            "gateway_type": "YOOKASSA",
        },
        headers=auth_headers,
    )

    assert response.status_code == 400


async def test_checkout_requires_authentication(client: httpx.AsyncClient, plan: PlanDto) -> None:
    response = await client.post(
        f"{API_V1}/payments/checkout",
        json={
            "plan_id": plan.id,
            "duration_days": 30,
            "currency": "RUB",
            "purchase_type": "NEW",
            "gateway_type": "YOOKASSA",
        },
    )

    assert response.status_code == 401
